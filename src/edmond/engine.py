"""Nonblocking percussion engine. No Qt, synth, DAW or MIDI clock dependency."""

from dataclasses import dataclass
import xml.etree.ElementTree as ET

from edmond.settings import Settings, valid_notes
from vega.input.state import PhysicalState
from vega.input.titan_profile import TitanPcDpProfile
from vega.midi.output import MidiOutput
from vega.model import ButtonChange, ButtonControl, FaceChange, FaceControl, LeverChange
from vega.runtime import DeviceStatus


@dataclass(frozen=True)
class DrumNote:
    note: int
    velocity: int
    offset: float = 0.0
    duration: float = 0.060


@dataclass(frozen=True)
class DrumPlan:
    notes: tuple[DrumNote, ...]


@dataclass
class HeldPad:
    pad: int
    next_repeat: float


class EdmondEngine:
    def __init__(self, settings: Settings, midi: MidiOutput | None = None):
        if not valid_notes(settings.notes):
            raise ValueError("Expected sixteen distinct MIDI notes")
        self.settings = settings
        self.midi = midi or MidiOutput(default_port="Edmond Drums Send")
        self.midi.set_channel(settings.channel)
        self.profile = TitanPcDpProfile()
        self.physical = PhysicalState()
        self.device = DeviceStatus(False)
        self.held: dict[str, HeldPad] = {}
        self.repeat = False
        self.hit_count = 0
        self.last_hit: tuple[int, int] | None = None
        self.lit_until: dict[int, float] = {}

    @property
    def velocity(self):
        return 127 if self.physical.lever_y > 0 else 55 if self.physical.lever_y < 0 else self.settings.velocity

    @property
    def interval(self):
        return 60 / self.settings.bpm * 4 / self.settings.division

    def hit(self, pad: int, now: float):
        if type(pad) is not int or not 0 <= pad < 16:
            raise ValueError("Pad must be 0–15")
        velocity = self.velocity
        self.midi.submit(DrumPlan((DrumNote(self.settings.notes[pad], velocity),)), now)
        self.lit_until[pad] = now + .11
        self.last_hit = (pad, velocity)
        self.hit_count += 1

    def press(self, source: str, pad: int, now: float):
        if source not in self.held:
            self.hit(pad, now)
            self.held[source] = HeldPad(pad, now + self.interval)

    def release(self, source: str):
        self.held.pop(source, None)

    def set_bank(self, bank: int):
        if bank not in (0, 1):
            raise ValueError("Bank must be 0 or 1")
        if bank != self.settings.bank:
            self.stop()
            self.settings.bank = bank

    def stop(self):
        # Keep physical edges: held buttons must be released before retriggering.
        self.held.clear()
        self.lit_until.clear()
        self.midi.panic()

    def set_repeat(self, enabled: bool, now: float):
        self.repeat = bool(enabled)
        for held in self.held.values():
            held.next_repeat = now + self.interval

    def receive(self, event, now: float):
        if isinstance(event, DeviceStatus):
            if event.connected != self.device.connected:
                self.stop()
                self.physical.reset()
                self.profile.reset()
            self.device = event
            return
        change = self.profile.translate(event)
        if change is None or not self.physical.apply(change):
            return
        if isinstance(change, FaceChange):
            key = change.face.name
            if change.pressed:
                self.press(key, list(FaceControl).index(change.face) + self.settings.bank * 8, now)
            else:
                self.release(key)
        elif isinstance(change, ButtonChange) and change.control is ButtonControl.OPTIONS and change.pressed:
            self.set_bank(1 - self.settings.bank)
        elif isinstance(change, LeverChange) and change.x:
            self.set_bank(0 if change.x < 0 else 1)

    def tick(self, now: float):
        if self.repeat:
            # A stalled GUI emits at most one repeat per pad, never a catch-up burst.
            pads = set()
            for held in tuple(self.held.values()):
                if now >= held.next_repeat:
                    pads.add(held.pad)
                    held.next_repeat = now + self.interval
            for pad in sorted(pads):
                self.hit(pad, now)
        self.midi.tick(now)

    def close(self):
        self.stop()
        self.midi.close()


def midi_map(settings: Settings, port: str = "Edmond Drums") -> str:
    """MPC desktop .xmm schema; 16 note-on bindings to pad targets A01–A16.

    Schema checked against Akai's bundled MPK mini 3 map; no device SysEx.
    Host import still needs verification in MPC Beats itself.
    """
    if not valid_notes(settings.notes):
        raise ValueError("Expected sixteen distinct MIDI notes")
    root = ET.Element("MidiLearnMap_", Manufacturer="Project Edmond", Version="0.1")
    device = ET.SubElement(root, "device")
    for direction in ("Input", "Output"):
        ET.SubElement(device, direction, UnixPortName=port, WindowsPortName=port)
    for pad, note in enumerate(settings.notes):
        pairing = ET.SubElement(root, "pairing")
        ET.SubElement(pairing, "Target_", Target_control=str(pad))
        ET.SubElement(pairing, "Mapping_", Mapping_type="1", Mapping_channel=str(settings.channel),
                      Mapping_data1=str(note), Mapping_control="4", Mapping_reverse="0")
    ET.indent(root)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"
