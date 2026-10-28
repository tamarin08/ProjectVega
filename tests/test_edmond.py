"""Deterministic controller-to-MIDI checks without hardware or a DAW."""

import json
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "src"))
from edmond.engine import EdmondEngine, midi_map
from edmond.settings import Settings, SettingsStore, DEFAULT_NOTES
from vega.input.events import RawAxisEvent, RawButtonEvent, RawHatEvent
from vega.midi.output import MidiOutput
from vega.runtime import DeviceStatus


class Midi:
    def __init__(self): self.messages = []
    def ports(self): return ("Vega Guitar","Edmond Drums")
    def open(self,name): self.name = name
    def send(self,message): self.messages.append(message)
    def close(self): pass


class EdmondTests(unittest.TestCase):
    def setUp(self):
        self.backend = Midi()
        self.output = MidiOutput(self.backend,default_port="Edmond Drums")
        self.output.restore("")
        self.engine = EdmondEngine(Settings(),self.output)
        self.backend.messages.clear()

    def ons(self):
        return [m for m in self.backend.messages if m.kind=="note_on"]

    def test_app_port_is_independent_and_channel_is_ten(self):
        self.assertEqual(self.output.port_name,"Edmond Drums")
        self.engine.receive(RawButtonEvent(2,True,1),1)
        self.engine.tick(1)
        self.assertEqual([(m.channel,m.note,m.velocity) for m in self.ons()],[(9,36,100)])

    def test_all_eight_verified_buttons_and_trigger_axes(self):
        for button in (2,3,5,4,0,1):
            self.engine.receive(RawButtonEvent(button,True,0),0)
        for axis in (5,4):
            self.engine.receive(RawAxisEvent(axis,0,0),0)
            self.engine.receive(RawAxisEvent(axis,1,0),0)
        self.engine.tick(0)
        self.assertEqual([m.note for m in self.ons()],list(range(36,44)))
        self.engine.tick(.061)
        self.assertFalse(self.output.active)

    def test_duplicate_edges_are_silent_and_velocity_uses_lever(self):
        self.engine.receive(RawHatEvent(0,0,1,0),0)
        self.engine.receive(RawButtonEvent(2,True,0),0)
        self.engine.receive(RawButtonEvent(2,True,0),0)
        self.engine.tick(0)
        self.assertEqual([m.velocity for m in self.ons()],[127])
        self.engine.receive(RawButtonEvent(2,False,.2),.2)
        self.engine.receive(RawHatEvent(0,0,-1,.2),.2)
        self.engine.receive(RawButtonEvent(2,True,.2),.2)
        self.engine.tick(.2)
        self.assertEqual(self.ons()[-1].velocity,55)

    def test_bank_changes_do_not_reinterpret_a_held_pad(self):
        self.engine.set_repeat(True,0)
        self.engine.receive(RawButtonEvent(2,True,0),0)
        self.engine.tick(0)
        self.engine.receive(RawButtonEvent(7,True,.01),.01)
        self.engine.receive(RawButtonEvent(7,True,.02),.02)
        self.assertEqual(self.engine.settings.bank,1)
        self.engine.tick(1)
        self.assertEqual(len(self.ons()),1)
        self.engine.receive(RawButtonEvent(2,False,1),1)
        self.engine.receive(RawButtonEvent(2,True,1),1)
        self.engine.tick(1)
        self.assertEqual(self.ons()[-1].note,44)

    def test_repeat_release_panic_disconnect_and_no_catchup(self):
        self.engine.set_repeat(True,0)
        self.engine.press("test",0,0)
        self.engine.tick(0)
        self.engine.tick(.149)
        self.assertEqual(len(self.ons()),1)
        self.engine.tick(.150)
        self.assertEqual(len(self.ons()),2)
        self.engine.tick(5)
        self.assertEqual(len(self.ons()),3)
        self.engine.release("test")
        self.engine.tick(6)
        self.assertEqual(len(self.ons()),3)
        self.engine.press("test",0,6)
        self.engine.tick(6)
        self.engine.stop()
        self.engine.tick(8)
        self.assertFalse(self.output.active)
        self.assertEqual(len(self.ons()),4)
        self.engine.receive(DeviceStatus(True),8)
        self.engine.receive(RawButtonEvent(2,True,8),8)
        self.engine.tick(8)
        self.engine.receive(DeviceStatus(False),8.01)
        self.engine.tick(10)
        self.assertEqual(len(self.ons()),5)
        self.assertFalse(self.engine.held)
        self.assertFalse(self.output.active)

    def test_unconnected_output_still_works_without_sound(self):
        self.output.select("")
        self.engine.press("test",15,0)
        self.engine.tick(0)
        self.assertEqual(self.engine.hit_count,1)
        self.assertFalse(self.ons())

    def test_bank_lever_and_custom_map(self):
        self.engine.receive(RawHatEvent(0,1,0,0),0)
        self.assertEqual(self.engine.settings.bank,1)
        self.engine.receive(RawHatEvent(0,-1,0,0),0)
        self.assertEqual(self.engine.settings.bank,0)
        settings = Settings(notes=tuple(range(60,76)),channel=3)
        root = ET.fromstring(midi_map(settings,"Edmond & Friends"))
        self.assertEqual(root.find("device/Input").get("WindowsPortName"),"Edmond & Friends")
        pairs = root.findall("pairing")
        self.assertEqual(len(pairs),16)
        for index,pair in enumerate(pairs):
            self.assertEqual(pair.find("Target_").get("Target_control"),str(index))
            self.assertEqual(pair.find("Mapping_").get("Mapping_data1"),str(index+60))
            self.assertEqual(pair.find("Mapping_").get("Mapping_channel"),"3")

    def test_settings_isolation_atomic_save_and_corrupt_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory)/"Edmond"/"settings.json")
            self.assertTrue(store.save(Settings(channel=4,extra={"future":12})))
            loaded = store.load()
            self.assertEqual(loaded.channel,4)
            self.assertEqual(loaded.extra,{"future":12})
            self.assertNotIn("repeat",json.loads(store.path.read_text()))
            store.path.write_text('{"notes":[1],"channel":true,"bpm":120,"division":7}')
            loaded = store.load()
            self.assertEqual(loaded.notes,DEFAULT_NOTES)
            self.assertEqual(loaded.channel,10)
            self.assertEqual(loaded.bpm,120)
            self.assertEqual(loaded.division,16)
            store.path.write_text("broken")
            self.assertEqual(store.load().notes,DEFAULT_NOTES)
            self.assertTrue(store.status)


if __name__ == "__main__":
    unittest.main()
