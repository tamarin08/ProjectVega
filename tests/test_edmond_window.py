"""Offscreen performance-control integration, using fake MIDI and no SDL."""

import os
from pathlib import Path
import tempfile
import time
import unittest
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "src"))
from qt_support import QtTestCase


class EdmondWindowTests(QtTestCase):
    def test_click_hold_panic_bank_and_channel_reach_midi(self):
        from PySide6.QtWidgets import QApplication
        from edmond.engine import EdmondEngine
        from edmond.settings import Settings, SettingsStore
        from edmond.window import EdmondWindow
        from vega.midi.output import MidiOutput
        from test_edmond import Midi
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as directory:
            backend = Midi()
            midi = MidiOutput(backend,default_port="Edmond Drums")
            engine = EdmondEngine(Settings(),midi)
            midi.restore("")
            store = SettingsStore(Path(directory)/"settings.json")
            window = EdmondWindow(engine,store)
            window.timer.stop()
            now = time.perf_counter()
            window.repeat.click()
            window.pads[0].pressed.emit()
            engine.tick(now+.01)
            engine.tick(now+1)
            self.assertEqual(len([m for m in backend.messages if m.kind=="note_on"]),2)
            window.pads[0].released.emit()
            engine.tick(now+2)
            self.assertFalse(engine.held)
            window.bank_buttons[1].click()
            self.assertEqual(engine.settings.bank,1)
            window.channel.setValue(3)
            self.assertEqual(engine.midi.channel,3)
            window.pads[8].click()
            engine.tick(now+3)
            ons = [m for m in backend.messages if m.kind=="note_on"]
            self.assertEqual((ons[-1].channel,ons[-1].note),(2,44))
            window.panic()
            self.assertFalse(engine.repeat)
            self.assertFalse(engine.midi.active)
            window.close()
            self.assertEqual(store.load().channel,3)
            self.assertEqual(store.load().bank,1)

    def test_note_editor_rejects_collisions_and_stages_cancel(self):
        from PySide6.QtWidgets import QApplication
        from edmond.settings import Settings
        from edmond.window import NoteEditor
        app = QApplication.instance() or QApplication([])
        settings = Settings()
        editor = NoteEditor(settings,None)
        editor.slots[0].setValue(37)
        editor.accept()
        self.assertTrue(editor.error.text())
        editor.reject()
        self.assertEqual(settings.notes[0],36)


if __name__ == "__main__":
    unittest.main()
