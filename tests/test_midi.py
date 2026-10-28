"""Deterministic MIDI scheduling through an in-memory transport."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vega.midi.output import MidiOutput, MidoBackend, MidiMessage, PygameMidiBackend
from test_preview import sample_plan
from vega.model import StrumCharacter, StrumDirection


class FakeMidi:
    def __init__(self):
        self.names = ("Vega Guitar", "Other")
        self.messages = []
        self.opened = ""
        self.fail = False

    def ports(self): return self.names
    def open(self, name): self.opened = name
    def send(self, message):
        if self.fail: raise OSError("port lost")
        self.messages.append(message)
    def close(self): self.opened = ""


class MidiTests(unittest.TestCase):
    def test_desktop_saved_external_output_survives_native_default(self):
        backend = FakeMidi()
        backend.names = ("Vega Guitar Send", "External device")
        output = MidiOutput(backend, default_port="Vega Guitar Send")
        output.restore("External device", prefer_default=False)
        self.assertEqual(output.port_name, "External device")
        output.close()

    def test_rapid_strums_eventually_pair_every_on_and_off(self):
        peak = 0
        for index in range(2000):
            now = index * .005
            self.output.submit(sample_plan(StrumCharacter.FULL), now)
            self.output.tick(now)
            peak = max(peak, len(self.output._queue))
        self.output.tick(20)
        balance = {}
        for message in self.backend.messages:
            if message.kind in ("note_on", "note_off"):
                key = message.channel, message.note
                balance[key] = balance.get(key, 0) + (1 if message.kind == "note_on" else -1)
                self.assertIn(balance[key], (0, 1))
        self.assertTrue(all(n == 0 for n in balance.values()))
        self.assertFalse(self.output.active)
        self.assertFalse(self.output._queue)
        self.assertLess(peak, 1200)  # Deadline horizon, not total session length.

    def test_port_switch_cancels_old_scheduled_notes(self):
        self.output.submit(sample_plan(), 1)
        self.output.tick(1)
        self.output.select("Other")
        self.assertFalse(self.output.active)
        self.assertFalse(self.output._queue)
        count = len(self.backend.messages)
        self.output.tick(10)
        self.assertEqual(len(self.backend.messages), count)
        self.assertEqual(self.backend.opened, "Other")

    def test_partial_panic_failure_attempts_remaining_cleanup(self):
        self.output.submit(sample_plan(), 1)
        self.output.tick(1)
        sent = []
        def send(message):
            sent.append(message)
            if len(sent) == 1:
                raise OSError("one send failed")
        with patch.object(self.backend, "send", side_effect=send), \
             patch.object(self.backend, "close", side_effect=OSError("close failed")):
            self.output.panic()
        self.assertTrue(any(m.channel == 15 and m.control == 120 for m in sent))
        self.assertFalse(self.output.active)
        self.assertFalse(self.output._queue)
        self.assertFalse(self.output.port_name)
        self.output.panic()
        self.output.close()

    def setUp(self):
        self.backend = FakeMidi()
        self.output = MidiOutput(self.backend)
        self.output.refresh()
        self.output.connect("Vega Guitar")

    def test_notes_follow_plan_deadlines_and_channel(self):
        self.output.set_channel(16)
        self.backend.messages.clear()
        plan = sample_plan(StrumCharacter.FULL, StrumDirection.RIGHT)
        self.output.submit(plan, 10)
        self.output.tick(9.99)
        self.assertFalse(self.backend.messages)
        for i, note in enumerate(plan.notes):
            self.output.tick(10 + note.offset)
            self.assertEqual(self.backend.messages[-1], MidiMessage("note_on", 15, note.note, note.velocity))
            self.assertEqual(len(self.backend.messages), i + 1)
        self.output.tick(10.799)
        self.assertEqual(len(self.output.active), 6)
        for note in plan.notes:
            self.output.tick(10 + note.offset + note.duration)
            self.assertEqual(self.backend.messages[-1], MidiMessage("note_off", 15, note.note))
        self.assertFalse(self.output.active)

    def test_retrigger_old_off_cannot_stop_new_note(self):
        plan = sample_plan()
        note = plan.notes[0]
        self.output.submit(plan, 0)
        self.output.tick(0)
        self.output.submit(plan, .4)
        self.output.tick(.4)
        kinds = [m.kind for m in self.backend.messages if m.note == note.note]
        self.assertEqual(kinds, ["note_on", "note_off", "note_on"])
        self.output.tick(note.duration)
        self.assertIn((0, note.note), self.output.active)
        self.output.tick(1.1)
        self.assertFalse(self.output.active)

    def test_panic_cancels_future_onsets_and_sends_all_notes_off(self):
        self.output.submit(sample_plan(), 1)
        self.output.tick(1)
        self.output.panic()
        self.assertFalse(self.output.active)
        count = len(self.backend.messages)
        self.output.tick(50)
        self.assertEqual(count, len(self.backend.messages))
        for ch in range(16):
            self.assertIn(MidiMessage("control_change", ch, control=123), self.backend.messages)
            self.assertIn(MidiMessage("control_change", ch, control=120), self.backend.messages)

    def test_channel_change_and_close_cancel_notes(self):
        self.output.submit(sample_plan(), 1)
        self.output.tick(1)
        self.output.set_channel(2)
        self.assertFalse(self.output.active)
        self.assertFalse(self.output._queue)
        self.output.submit(sample_plan(), 2)
        self.output.tick(2)
        self.output.close()
        self.assertFalse(self.output.active)
        self.assertEqual(self.backend.opened, "")

    def test_invalid_channels(self):
        for value in (0, 17, 1.5):
            with self.assertRaises(ValueError): self.output.set_channel(value)

    def test_port_disappearance_panics_and_does_not_auto_reconnect(self):
        self.output.submit(sample_plan(), 1)
        self.output.tick(1)
        self.backend.names = ()
        self.output.tick(3)
        self.assertFalse(self.output.active)
        self.assertFalse(self.output.port_name)
        self.assertIn("disappeared", self.output.status)
        self.backend.names = ("Vega Guitar",)
        self.output.refresh()
        self.assertFalse(self.output.port_name)

    def test_send_failure_contained_and_queue_cleared(self):
        self.backend.fail = True
        self.output.submit(sample_plan(), 1)
        self.output.tick(1)
        self.assertIn("port lost", self.output.status)
        self.assertFalse(self.output._queue)
        self.assertFalse(self.output.active)
        self.assertFalse(self.output.port_name)

    def test_missing_backend_and_failed_open_do_not_escape(self):
        with patch.object(self.backend, "ports", side_effect=ImportError("install MIDI extra")):
            self.output.refresh()
        self.assertIn("install MIDI extra", self.output.status)
        self.output.submit(sample_plan(), 0)
        self.assertFalse(self.output._queue)
        with patch.object(self.backend, "open", side_effect=OSError("port busy")):
            self.output.connect("Vega Guitar")
        self.assertIn("port busy", self.output.status)

    def test_no_ports_is_useful_and_not_an_error(self):
        self.output.disconnect()
        self.backend.names = ()
        self.output.refresh()
        self.assertEqual("No MIDI outputs available", self.output.status)

    def test_mido_adapter_uses_existing_port_and_normal_messages(self):
        sent = []
        opened = []
        port = SimpleNamespace(send=sent.append, close=lambda: None)
        api = SimpleNamespace(get_output_names=lambda: ["Vega Guitar"],
                              open_output=lambda name: opened.append(name) or port)
        mido = SimpleNamespace(Backend=lambda name: api, Message=lambda kind, **kw: (kind, kw))
        with patch.dict(sys.modules, {"mido": mido, "rtmidi": SimpleNamespace()}):
            backend = MidoBackend()
            self.assertEqual(backend.ports(), ("Vega Guitar",))
            backend.open("Vega Guitar")
            backend.send(MidiMessage("note_on", 0, 64, 100))
            backend.send(MidiMessage("control_change", 0, control=123))
            backend.close()
        self.assertEqual(opened, ["Vega Guitar"])
        self.assertEqual(sent[0], ("note_on", {"channel": 0, "note": 64, "velocity": 100}))
        self.assertEqual(sent[1][1]["control"], 123)

    def test_portmidi_fallback_enumeration_encoding_and_lifecycle(self):
        class Api:
            def __init__(self):
                self.initialized = False
                self.sent = []
                self.opened = []
            def get_init(self): return self.initialized
            def init(self): self.initialized = True
            def quit(self): self.initialized = False
            def get_count(self): return 3
            def get_device_info(self, i):
                return (b"MMSystem", b"Vega Guitar", i == 0, i != 0, False)
            def Output(self, index, latency):
                self.opened.append((index, latency))
                return SimpleNamespace(write_short=lambda *data: self.sent.append(data), close=lambda: None)
        api = Api()
        backend = PygameMidiBackend()
        backend.api = api
        self.assertEqual(backend.ports(), ("Vega Guitar [1]", "Vega Guitar [2]"))
        backend.open("Vega Guitar [2]")
        mido = SimpleNamespace(Message=lambda kind, **fields: SimpleNamespace(
            bytes=lambda: [0x90 + fields["channel"], fields["note"], fields["velocity"]]))
        with patch.dict(sys.modules, {"mido": mido}):
            backend.send(MidiMessage("note_on", 2, 60, 90))
        self.assertEqual(api.opened, [(2, 0)])
        self.assertEqual(api.sent, [(0x92, 60, 90)])
        backend.close()
        self.assertFalse(api.initialized)

    def test_missing_rtmidi_selects_compiler_free_transport(self):
        with patch.dict(sys.modules, {"mido": SimpleNamespace(), "rtmidi": None}), \
             patch.object(PygameMidiBackend, "ports", return_value=("Vega Guitar",)):
            backend = MidoBackend()
            self.assertEqual(backend.ports(), ("Vega Guitar",))
            self.assertIsInstance(backend.fallback, PygameMidiBackend)

    def test_startup_prefers_exact_vega_then_saved_never_arbitrary(self):
        self.output.disconnect()
        self.output.restore("Other")
        self.assertEqual(self.output.port_name, "Vega Guitar")
        self.output.disconnect()
        self.backend.names = ("Other", "Microsoft GS Wavetable Synth")
        self.output.restore("Other")
        self.assertEqual(self.output.port_name, "Other")
        self.output.disconnect()
        self.output.restore("Missing")
        self.assertEqual(self.output.port_name, "")
        self.assertIn("no longer available", self.output.status)
        self.output.restore("")
        self.assertEqual(self.output.port_name, "")

    def test_refresh_cleans_notes_reopens_same_port_and_remembers_missing(self):
        self.output.select("Other")
        self.output.submit(sample_plan(), 1)
        self.output.tick(1)
        self.output.refresh(rescan=True)
        self.assertEqual(self.output.port_name, "Other")
        self.assertFalse(self.output.active)
        self.assertFalse(self.output._queue)
        self.backend.names = ("Vega Guitar",)
        self.output.refresh(rescan=True)
        self.assertFalse(self.output.port_name)
        self.assertIn("disappeared", self.output.status)
        self.backend.names = ("Other",)
        self.output.refresh(rescan=True)
        self.assertEqual(self.output.port_name, "Other")
        self.output.select("")
        self.output.refresh(rescan=True)
        self.assertFalse(self.output.port_name)

    def test_all_characters_directions_channels_and_repeat_panic(self):
        for channel in (1, 16):
            self.output.set_channel(channel)
            for character in StrumCharacter:
                for direction in StrumDirection:
                    self.backend.messages.clear()
                    plan = sample_plan(character, direction)
                    self.output.submit(plan, 100)
                    for note in plan.notes:
                        self.output.tick(100 + note.offset)
                    ons = [m for m in self.backend.messages if m.kind == "note_on"]
                    self.assertEqual([m.note for m in ons], [n.note for n in plan.notes])
                    self.assertEqual([m.velocity for m in ons], [n.velocity for n in plan.notes])
                    self.assertTrue(all(m.channel == channel - 1 for m in ons))
                    self.output.tick(102)
                    self.assertEqual(len([m for m in self.backend.messages if m.kind == "note_off"]), len(plan.notes))
                    self.output.panic()
                    self.output.panic()
                    self.assertFalse(self.output.active)
                    self.assertFalse(self.output._queue)

    def test_native_inventory_change_requests_safe_rescan_only_every_two_seconds(self):
        with patch.object(self.backend, "ports_changed", create=True, return_value=True) as check:
            self.output.submit(sample_plan(), 1)
            self.output.tick(1)
            self.assertEqual(check.call_count, 1)
            self.assertFalse(self.output._queue)
            self.output.tick(2)
            self.assertEqual(check.call_count, 1)
            self.output.tick(3)
            self.assertEqual(check.call_count, 2)

    def test_portmidi_change_signature_does_not_close_live_handle(self):
        backend = PygameMidiBackend()
        backend._signature = ((1, 2, "Cable", 1),)
        with patch("vega.midi.output.output_signature", return_value=backend._signature):
            self.assertFalse(backend.ports_changed())
        with patch("vega.midi.output.output_signature", return_value=()):
            self.assertTrue(backend.ports_changed())
