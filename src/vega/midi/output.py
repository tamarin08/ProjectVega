"""Existing-port MIDI routing; adapters lazily load libraries, never Qt/a DAW."""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Protocol

from vega.midi.windows_ports import output_signature


class TimedNote(Protocol):
    note: int
    velocity: int
    offset: float
    duration: float


class NotePlan(Protocol):
    @property
    def notes(self) -> tuple[TimedNote, ...]: ...


@dataclass(frozen=True)
class MidiMessage:
    kind: str
    channel: int  # MIDI wire convention: 0–15. UI uses 1–16.
    note: int = 0
    velocity: int = 0
    control: int = 0
    value: int = 0


class MidiBackend(Protocol):
    def ports(self) -> tuple[str, ...]: ...
    def open(self, name: str) -> None: ...
    def send(self, message: MidiMessage) -> None: ...
    def close(self) -> None: ...


class MidoBackend:
    """Lazy imports allow the rest of Vega to work without the MIDI extra."""

    def __init__(self) -> None:
        self.port = None
        self.backend = None
        self.fallback = None

    def _load(self) -> None:
        if self.backend is None:
            import mido
            self.mido = mido
            try:
                import rtmidi  # Optional: released Windows wheels currently stop at Python 3.12.
            except (ImportError, OSError):
                self.fallback = PygameMidiBackend()
                self.backend = self.fallback
            else:
                self.backend = mido.Backend("mido.backends.rtmidi")

    def ports(self) -> tuple[str, ...]:
        self._load()
        if self.fallback:
            return self.fallback.ports()
        return tuple(self.backend.get_output_names())

    def open(self, name: str) -> None:
        self._load()
        if self.fallback:
            self.fallback.open(name)
            return
        self.port = self.backend.open_output(name)  # Deliberately NOT virtual=True.

    def ports_changed(self) -> bool:
        return bool(self.fallback and self.fallback.ports_changed())

    def send(self, message: MidiMessage) -> None:
        if self.fallback:
            self.fallback.send(message)
            return
        if self.port is None:
            raise RuntimeError("MIDI port is closed")
        fields = {"channel": message.channel}
        if message.kind == "control_change":
            fields.update(control=message.control, value=message.value)
        else:
            fields.update(note=message.note, velocity=message.velocity)
        self.port.send(self.mido.Message(message.kind, **fields))

    def close(self) -> None:
        if self.fallback:
            self.fallback.close()
        port, self.port = self.port, None
        if port is not None:
            port.close()


class PygameMidiBackend:
    """PortMidi already ships with pygame's Python 3.13 Windows wheel.

    This is only a transport fallback, not a second music engine. Mido still
    validates/encodes messages. Output latency=0; the shared scheduler times it.
    """

    def __init__(self) -> None:
        self.api = None
        self.port = None
        self._signature = None

    def _devices(self) -> dict[str, int]:
        if self.api is None:
            import pygame.midi
            self.api = pygame.midi
        if not self.api.get_init():
            self.api.init()
        found = []
        for index in range(self.api.get_count()):
            info = self.api.get_device_info(index)
            if info is not None and info[3]:
                name = info[1].decode("utf-8", errors="replace")
                found.append((name, index))
        # Preserve friendly names normally; disambiguate duplicate output names.
        return {(name if sum(n == name for n, _ in found) == 1 else f"{name} [{index}]"): index
                for name, index in found}

    def ports(self) -> tuple[str, ...]:
        # PortMidi caches its device list at initialization. Reinitialize only
        # while disconnected: doing so with an open output would invalidate it.
        if self.api is not None and self.port is None:
            self.api.quit()
        return tuple(self._devices())

    def open(self, name: str) -> None:
        devices = self._devices()
        if name not in devices:
            raise OSError("MIDI port is no longer available; press Refresh")
        self.port = self.api.Output(devices[name], latency=0)
        self._signature = output_signature()

    def ports_changed(self) -> bool:
        return self._signature != output_signature()

    def send(self, message: MidiMessage) -> None:
        import mido
        if self.port is None:
            raise OSError("MIDI port is closed")
        fields = {"channel": message.channel}
        if message.kind == "control_change":
            fields.update(control=message.control, value=message.value)
        else:
            fields.update(note=message.note, velocity=message.velocity)
        self.port.write_short(*mido.Message(message.kind, **fields).bytes())

    def close(self) -> None:
        port, self.port = self.port, None
        try:
            if port is not None:
                port.close()
        finally:
            if self.api is not None:
                self.api.quit()


class MidiOutput:
    """Tick-driven queue. Inject 'now' in seconds; never sleep for a note.

    Each note-on owns a generation token. An older scheduled note-off cannot
    cut off a retrigger. Port/channel changes cancel queued events and panic.
    """

    def __init__(self, backend: MidiBackend | None = None, *, default_port: str = "Vega Guitar") -> None:
        self.backend = backend or MidoBackend()
        self.default_port = default_port
        self.port_names: tuple[str, ...] = ()
        self.port_name = ""
        self.status = "Not connected · select an existing MIDI output"
        self.channel = 1
        self.active: dict[tuple[int, int], int] = {}
        self._queue: list[tuple] = []
        self._serial = 0
        self._next_scan = 0.0
        self.preferred_port = ""

    def restore(self, saved_port: str, *, prefer_default: bool = True) -> None:
        """Startup only: exact app port wins; never pick an arbitrary synth."""
        self.refresh()
        self.preferred_port = (self.default_port if self.default_port in self.port_names
                               and (prefer_default or not saved_port) else saved_port)
        if self.preferred_port in self.port_names:
            self.connect(self.preferred_port)
        elif self.preferred_port:
            self.status = f"Selected MIDI port is no longer available · {self.preferred_port}"

    def select(self, name: str) -> None:
        self.preferred_port = name
        self.connect(name)

    def refresh(self, *, rescan: bool = False) -> None:
        # PortMidi caches its list. Explicit Refresh stops notes and closes the
        # handle before reinitialization, then reopens the same chosen port.
        wanted = self.port_name or self.preferred_port
        if rescan:
            self.disconnect()
        try:
            self.port_names = self.backend.ports()
            if self.port_name and self.port_name not in self.port_names:
                self.disconnect()
                self.status = "Port disappeared · reconnect after Refresh"
            elif not self.port_name:
                self.status = "Not connected · select a port" if self.port_names else "No MIDI outputs available"
            if rescan and wanted:
                if wanted in self.port_names:
                    self.connect(wanted)
                else:
                    self.status = f"Port disappeared · {wanted} · reconnect after Refresh"
        except Exception as exc:
            self._failed(exc)
            self.port_names = ()

    def connect(self, name: str) -> None:
        if name and name == self.port_name:
            return
        self.disconnect()
        if not name:
            return
        try:
            self.preferred_port = name
            self.backend.open(name)
            self.port_name = name
            self.status = f"Connected · {name}"
        except Exception as exc:
            self._failed(exc)

    def set_channel(self, channel: int) -> None:
        if type(channel) is not int or not 1 <= channel <= 16:
            raise ValueError("MIDI channel must be 1–16")
        if channel != self.channel:
            self.panic()
            self.channel = channel

    def submit(self, plan: NotePlan, now: float) -> None:
        if not self.port_name:
            return
        for note in plan.notes:
            self._serial += 1
            token = self._serial
            channel = self.channel - 1
            heapq.heappush(self._queue, (now + note.offset, token, True, channel, note.note, note.velocity))
            heapq.heappush(self._queue, (now + note.offset + note.duration, token, False, channel, note.note, 0))

    def tick(self, now: float) -> None:
        try:
            if self.port_name and now >= self._next_scan:
                self._next_scan = now + 2.0
                changed = getattr(self.backend, "ports_changed", lambda: False)()
                self.refresh(rescan=changed)
            while self._queue and self._queue[0][0] <= now:
                deadline, token, on, channel, note, velocity = heapq.heappop(self._queue)
                key = (channel, note)
                if on:
                    if key in self.active:
                        self.backend.send(MidiMessage("note_off", channel, note))
                    self.backend.send(MidiMessage("note_on", channel, note, velocity))
                    self.active[key] = token
                elif self.active.get(key) == token:
                    self.backend.send(MidiMessage("note_off", channel, note))
                    del self.active[key]
        except Exception as exc:
            self._failed(exc)

    def _cleanup(self) -> None:
        """Best effort: continue cleanup even if an individual send fails."""
        self._queue.clear()
        messages = [MidiMessage("note_off", ch, note) for ch, note in self.active]
        self.active.clear()
        if self.port_name:
            for ch in range(16):
                messages.extend(MidiMessage("control_change", ch, control=cc) for cc in (64, 123, 120))
        first_error = None
        for message in messages:
            try:
                self.backend.send(message)
            except Exception as exc:
                first_error = first_error or exc
        if first_error:
            raise first_error

    def panic(self) -> None:
        try:
            self._cleanup()
        except Exception as exc:
            self._failed(exc)

    def _failed(self, exc: Exception) -> None:
        try:
            self._cleanup()
        except Exception:
            pass
        try:
            self.backend.close()
        except Exception:
            pass
        self.port_name = ""
        self.status = f"MIDI unavailable: {exc}"

    def disconnect(self) -> None:
        self.panic()
        try:
            self.backend.close()
        except Exception as exc:
            self.status = f"MIDI close failed: {exc}"
        else:
            self.status = "Not connected · select a port"
        self.port_name = ""

    def close(self) -> None:
        self.disconnect()
