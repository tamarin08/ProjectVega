"""Shared native connection controller for the two desktop windows."""

import time
import subprocess
import json
import os
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QFileDialog

from vega.midi.native_route import ensure_route, VEGA_ROUTE, EDMOND_ROUTE
from vega.midi.host_setup import host_executable, install_fl_profile, install_mpc_profile, launch_host, process_running


class DawConnection(QObject):
    status_changed = Signal(str)

    def __init__(self, parent, midi, host, apply_port, stop, save, map_factory=None):
        super().__init__(parent)
        self.midi, self.host = midi, host
        self.apply_port, self.stop, self.save = apply_port, stop, save
        self.map_factory = map_factory
        self.spec = VEGA_ROUTE if host == "fl" else EDMOND_ROUTE
        self.status = "Native MIDI is available through Add to " + ("FL Studio" if host == "fl" else "MPC")
        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.finish_route)
        self.deadline = 0
        self.host_after_route = False
        self.route_result = None
        self._fl_confirmed = False
        self.pending_host = None
        self.host_timer = QTimer(self)
        self.host_timer.setInterval(1000)
        self.host_timer.timeout.connect(self.finish_host_restart)
        self.status_timer = QTimer(self)
        self.status_timer.setInterval(1000)
        self.status_timer.timeout.connect(self.check_host_status)

    def publish(self, text):
        self.status = text
        self.status_changed.emit(text)

    def connect_native(self, *, add_host=False):
        self.stop()
        self.host_after_route = add_host
        try:
            self.route_result = ensure_route(self.spec)
            self.deadline = time.perf_counter() + 12
            self.finish_route()
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            self.publish(str(exc))

    def finish_route(self):
        self.midi.refresh(rescan=True)
        if self.spec.send_name in self.midi.port_names:
            self.timer.stop()
            self.apply_port(self.spec.send_name)
            self.save()
            if self.midi.port_name != self.spec.send_name:
                self.publish(self.midi.status)
                return
            self.publish("Native MIDI connected · DAW input: " + self.spec.host_name)
            if self.host == "fl":
                self.status_timer.start()
            if self.host_after_route:
                self.host_after_route = False
                self.add_host()
        elif time.perf_counter() < self.deadline:
            self.publish("Windows is creating the MIDI ports…")
            self.timer.start()
        else:
            self.timer.stop()
            self.publish("Windows did not expose the MIDI ports. Update Windows and retry Add to "
                         + ("FL Studio" if self.host == "fl" else "MPC") + ".")

    def add_host(self):
        try:
            executable = host_executable(self.host)
            if executable is None:
                path, _ = QFileDialog.getOpenFileName(self.parent(), "Select your installed DAW", "",
                                                      "Windows application (*.exe)")
                if not path:
                    self.publish("Native MIDI connected · Install your DAW, then click Add again.")
                    return
                executable = Path(path)
            running = process_running(executable)
            if self.host == "fl":
                install_fl_profile()
                message = "Added to FL Studio · Vega Guitar auto-detect profile installed."
            else:
                profile, applied = install_mpc_profile(self.map_factory(), executable, running=running)
                message = ("Added to MPC · Edmond Drums input and pad profile configured." if applied else
                           "Edmond profile installed · In MPC, enable Edmond Drums and select the Edmond map.")
            if running:
                self.pending_host = executable
                self.host_timer.start()
                self.publish("Profile installed · Close " + ("FL Studio" if self.host == "fl" else "MPC")
                             + " when ready; this app will finish setup and reopen it.")
                return
            launch_host(executable)
            self.publish(message)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            self.publish("Native MIDI connected · Host setup: " + str(exc))

    def finish_host_restart(self):
        try:
            if self.pending_host is None or process_running(self.pending_host):
                return
            executable, self.pending_host = self.pending_host, None
            self.host_timer.stop()
            if self.host == "mpc":
                install_mpc_profile(self.map_factory(), executable, running=False)
            launch_host(executable)
            self.publish("Added to " + ("FL Studio" if self.host == "fl" else "MPC")
                         + " · Native MIDI connected.")
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            self.host_timer.stop()
            self.publish("Host setup: " + str(exc))

    def close(self):
        self.timer.stop()
        self.host_timer.stop()
        self.status_timer.stop()

    def check_host_status(self):
        if self.pending_host is not None:
            return
        try:
            path = Path(os.environ["LOCALAPPDATA"]) / "ProjectVega/fl-connection.json"
            status = json.loads(path.read_text())
            if (status.get("app") == "ProjectVega" and status.get("online") is True
                    and 0 <= time.time() - status.get("time", 0) < 4):
                self._fl_confirmed = True
                count = status.get("note_on_count", 0)
                self.publish(f"FL Studio receiving Vega MIDI · {count} notes" if count else
                             "FL Studio connected · Select an instrument to play.")
            elif self._fl_confirmed:
                self._fl_confirmed = False
                self.publish("FL Studio disconnected · Add to FL Studio to reopen it.")
        except (OSError, ValueError, TypeError, AttributeError, KeyError):
            pass
