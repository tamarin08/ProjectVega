"""Connection setup waits for a running DAW instead of discarding user work."""

import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
from unittest.mock import Mock, patch
from qt_support import QtTestCase


class DawConnectionTests(QtTestCase):
    def test_running_host_is_configured_after_exit_then_reopened_once(self):
        from PySide6.QtWidgets import QApplication, QWidget
        from vega.app.daw_connection import DawConnection
        from vega.midi.output import MidiOutput
        from test_edmond import Midi
        app = QApplication.instance() or QApplication([])
        parent = QWidget()
        backend = Midi()
        backend.ports = lambda: ("Vega Guitar Send", "Vega Guitar")
        output = MidiOutput(backend)
        save = Mock()
        helper = DawConnection(parent, output, "fl", output.select, output.panic, save)
        with patch("vega.app.daw_connection.ensure_route", return_value={"success": True}), \
                patch("vega.app.daw_connection.host_executable", return_value=Path("FL64.exe")), \
                patch("vega.app.daw_connection.install_fl_profile") as install, \
                patch("vega.app.daw_connection.process_running", side_effect=[True, True, False]), \
                patch("vega.app.daw_connection.launch_host") as launch:
            helper.connect_native(add_host=True)
            self.assertEqual(output.port_name, "Vega Guitar Send")
            self.assertTrue(helper.host_timer.isActive())
            launch.assert_not_called()
            helper.finish_host_restart()
            launch.assert_not_called()
            helper.finish_host_restart()
            launch.assert_called_once_with(Path("FL64.exe"))
            install.assert_called_once()
            self.assertFalse(helper.host_timer.isActive())
        helper.close()
        output.close()
        parent.close()
