"""Compact control panel; widgets observe runtime state and send settings."""

from __future__ import annotations

import time

from PySide6.QtCore import QByteArray, QTimer, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QBoxLayout, QComboBox, QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLayout, QMainWindow,
    QPushButton, QScrollArea, QSizePolicy, QSlider, QSpinBox, QStatusBar, QVBoxLayout, QWidget,
)

from vega.app.style import STYLE
from vega.app.widgets import FaceBank, GlassPanel, LeverView, VegaMark
from vega.app.identity import APP_NAME, icon_path
from vega.app.geometry import initial_size
from vega.app.fret_set_editor import FretSetEditor
from vega.music.harmony import BankAction, note_name
from vega.runtime import VegaRuntime
from vega.settings import SettingsStore


def label(text: str, role: str = "") -> QLabel:
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setObjectName(role)
    widget.setWordWrap(True)
    return widget


def panel(title: str) -> tuple[QFrame, QVBoxLayout]:
    frame = GlassPanel()
    frame.setObjectName("panel")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 14, 18, 14)
    layout.setSpacing(9)
    caption = label(title, "section")
    caption.setFixedHeight(20)
    layout.addWidget(caption)
    return frame, layout


class VegaWindow(QMainWindow):
    def __init__(self, runtime: VegaRuntime, store: SettingsStore) -> None:
        super().__init__()
        self.runtime = runtime
        self.store = store
        self.previous = None
        self._closing = False
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(str(icon_path())))
        available = self.screen().availableGeometry()
        self.resize(*initial_size(available.width(), available.height()))
        self.setMinimumSize(min(400, available.width()), min(300, available.height()))
        self.move(available.x() + 24, available.y() + 24)
        geometry = runtime.settings.window_geometry
        if geometry:
            self.restoreGeometry(QByteArray.fromBase64(geometry.encode("ascii", errors="ignore")))
            self.resize(min(self.width(), available.width() - 24), min(self.height(), available.height() - 64))
            self.move(max(available.x(), min(self.x(), available.right() - self.width() - 16)),
                      max(available.y(), min(self.y(), available.bottom() - self.height() - 40)))
        self.setStyleSheet(STYLE)
        body = QWidget()
        body.setObjectName("body")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(body)
        self.setCentralWidget(scroll)
        outer = QVBoxLayout(body)
        outer.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        outer.setContentsMargins(16, 12, 16, 14)
        outer.setSpacing(10)

        header = QHBoxLayout()
        header.addWidget(VegaMark())
        brand = QVBoxLayout()
        title = label("Vega")
        title.setStyleSheet("font-size: 24px; font-weight: 400; color: #e3d9cc;")
        brand.addWidget(title)
        brand.addWidget(label("Guitar controller", "muted"))
        header.addLayout(brand)
        header.addStretch()
        outer.addLayout(header)

        device_panel, device_layout = panel("Device")
        row = QHBoxLayout()
        self.device_name = label("Qanba Titan")
        self.device_status = label("Waiting for Titan", "status")
        self.device_status.setWordWrap(True)
        row.addWidget(self.device_name)
        row.addStretch()
        row.addWidget(self.device_status)
        device_layout.addLayout(row)
        device_layout.addWidget(label("Profile: Qanba Titan PC+DP    |    Controller switches: PC + DP", "muted"))
        outer.addWidget(device_panel)

        controls = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.controls_layout = controls
        controls.setSpacing(12)
        faces_panel, faces_layout = panel("FRET SET")
        self.set_name = label("", "value")
        faces_layout.addWidget(self.set_name)
        bank_row = QHBoxLayout()
        self.bank_previous = QPushButton("Previous")
        self.bank_next = QPushButton("Next")
        self.bank_label = label("Set 1 of 3", "muted")
        bank_row.addWidget(self.bank_previous)
        bank_row.addWidget(self.bank_label, 1)
        bank_row.addWidget(self.bank_next)
        faces_layout.addLayout(bank_row)
        self.faces = FaceBank()
        faces_layout.addWidget(self.faces)
        self.held_frets = label("Held frets: Open", "muted")
        self.bank_pending = label("", "muted")
        faces_layout.addWidget(self.held_frets)
        faces_layout.addWidget(self.bank_pending)
        self.bank_next.setToolTip("Options also advances the set. Changes wait for held buttons and pending strokes.")
        self.edit_sets = QPushButton("Edit Fret Sets...")
        faces_layout.addWidget(self.edit_sets)
        faces_layout.addStretch()
        controls.addWidget(faces_panel, 1)
        lever_panel, lever_layout = panel("Lever")
        lever_panel.setMinimumHeight(286)
        self.lever = LeverView()
        lever_layout.addWidget(self.lever)
        lever_layout.addWidget(label("Left/right: strum    |    Vertical center: NORMAL", "muted"))
        controls.addWidget(lever_panel, 1)
        outer.addLayout(controls)

        harmony_panel, harmony_layout = panel("Virtual guitar")
        self.harmony = label("Open strings", "value")
        harmony_layout.addWidget(self.harmony)
        self.strings_layout = QGridLayout()
        self.string_labels = [label("", "muted") for _ in range(6)]
        for i, widget in enumerate(self.string_labels):
            self.strings_layout.addWidget(widget, 0, i)
        harmony_layout.addLayout(self.strings_layout)
        outer.addWidget(harmony_panel)

        last_panel, last_layout = panel("Last strum")
        self.strum = label("Waiting for a strum", "value")
        self.fingering = label("Held at stroke: none", "muted")
        self.strum_meta = label("Strums: 0", "muted")
        last_layout.addWidget(self.strum)
        last_layout.addWidget(self.fingering)
        last_layout.addWidget(self.strum_meta)
        outer.addWidget(last_panel)

        lower = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.lower_layout = lower
        lower.setSpacing(12)
        timing_panel, timing_layout = panel("Timing")
        timing_row = QHBoxLayout()
        timing_row.addWidget(label("Gesture settle"))
        self.settle = QDoubleSpinBox()
        self.settle.setRange(0, 20)
        self.settle.setDecimals(1)
        self.settle.setSingleStep(1)
        self.settle.setSuffix(" ms")
        self.settle.setValue(runtime.settings.settle_ms)
        self.settle.setAccessibleName("Production recognizer settle window in milliseconds")
        timing_row.addWidget(self.settle)
        timing_layout.addLayout(timing_row)
        presets = QHBoxLayout()
        for value in (4, 6, 8, 10, 12):
            button = QPushButton(str(value))
            button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            button.setToolTip(f"Set the production settle window to {value} ms")
            button.clicked.connect(lambda checked=False, ms=value: self.settle.setValue(ms))
            presets.addWidget(button)
        timing_layout.addLayout(presets)
        timing_layout.addWidget(label("Default: 8 ms", "muted"))
        spread_row = QHBoxLayout()
        spread_row.addWidget(label("String spread"))
        self.spread = QDoubleSpinBox()
        self.spread.setRange(1, 30)
        self.spread.setDecimals(1)
        self.spread.setSuffix(" ms")
        self.spread.setValue(runtime.settings.spread_ms)
        self.spread.setToolTip("Musical delay between strings; independent of gesture settling")
        spread_row.addWidget(self.spread)
        timing_layout.addLayout(spread_row)
        lower.addWidget(timing_panel, 1)

        audio_panel, audio_layout = panel("Preview audio")
        audio_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.audio_buttons_layout = audio_row
        self.mute = QPushButton("Unmute preview")
        self.mute.setObjectName("mute")
        self.mute.setCheckable(True)
        self.mute.setChecked(True)
        self.panic = QPushButton("Panic / Stop")
        self.panic.setToolTip("Stop all preview and MIDI notes immediately. Future strums may sound.")
        audio_row.addWidget(self.mute)
        audio_row.addWidget(self.panic)
        audio_layout.addLayout(audio_row)
        volume_row = QHBoxLayout()
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(round(runtime.preview.volume * 100))
        self.volume.setAccessibleName("Preview volume")
        self.volume_value = label(f"{self.volume.value()}%", "muted")
        volume_row.addWidget(label("Volume", "muted"))
        volume_row.addWidget(self.volume)
        volume_row.addWidget(self.volume_value)
        audio_layout.addLayout(volume_row)
        self.audio_status = label(runtime.preview.status, "muted")
        self.audio_status.setWordWrap(True)
        audio_layout.addWidget(self.audio_status)
        lower.addWidget(audio_panel, 1)
        outer.addLayout(lower)

        midi_panel, midi_layout = panel("MIDI output")
        port_row = QHBoxLayout()
        port_row.addWidget(label("Port"))
        self.midi_port = QComboBox()
        self.midi_port.setAccessibleName("Existing MIDI output port")
        self.midi_port.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.midi_port.setMinimumContentsLength(12)
        self.midi_port.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.midi_refresh = QPushButton("Refresh")
        self.midi_refresh.setToolTip("Stop MIDI notes, rescan ports and reconnect the selected output if available.")
        port_row.addWidget(self.midi_port, 1)
        port_row.addWidget(self.midi_refresh)
        midi_layout.addLayout(port_row)
        self.midi_status = label(runtime.midi.status, "muted")
        midi_layout.addWidget(self.midi_status)
        self.add_fl = QPushButton("Add to FL Studio")
        midi_layout.addWidget(self.add_fl)
        self.daw_status = label("Built-in MIDI routing · no separate loopback utility", "muted")
        midi_layout.addWidget(self.daw_status)
        channel_row = QHBoxLayout()
        channel_row.addWidget(label("Channel"))
        self.midi_channel = QSpinBox()
        self.midi_channel.setRange(1, 16)
        self.midi_channel.setValue(runtime.midi.channel)
        channel_row.addWidget(self.midi_channel)
        channel_row.addStretch()
        self.midi_panic = QPushButton("Panic")
        channel_row.addWidget(self.midi_panic)
        midi_layout.addLayout(channel_row)
        outer.addWidget(midi_panel)

        status_bar = QStatusBar()
        status_bar.showMessage("PC + DP · Native Windows MIDI routing")
        self.setStatusBar(status_bar)
        self.settings_status = label(store.error, "muted")
        self.settings_status.setWordWrap(True)
        self.settings_status.setVisible(bool(store.error))
        outer.addWidget(self.settings_status)

        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(400)
        self.save_timer.timeout.connect(self.save_settings)
        self.flash_timer = QTimer(self)
        self.flash_timer.setSingleShot(True)
        self.flash_timer.setInterval(140)
        self.flash_timer.timeout.connect(lambda: self.strum.setStyleSheet(""))
        self.settle.valueChanged.connect(self.change_settle)
        self.spread.valueChanged.connect(self.change_spread)
        self.volume.valueChanged.connect(self.change_volume)
        self.mute.toggled.connect(self.change_mute)
        self.panic.clicked.connect(runtime.panic)
        self.bank_previous.clicked.connect(lambda: self.change_bank(BankAction.BANK_PREVIOUS))
        self.bank_next.clicked.connect(lambda: self.change_bank(BankAction.BANK_NEXT))
        self.edit_sets.clicked.connect(self.open_set_editor)
        self.midi_refresh.clicked.connect(self.refresh_ports)
        self.midi_port.activated.connect(self.connect_port)
        self.midi_channel.valueChanged.connect(self.change_midi_channel)
        self.midi_panic.clicked.connect(runtime.panic)
        from vega.app.daw_connection import DawConnection
        self.native_connection = DawConnection(self, runtime.midi, "fl", runtime.connect_midi,
                                                runtime.panic, self.save_settings)
        self.native_connection.status_changed.connect(self.daw_status.setText)
        self.add_fl.clicked.connect(lambda: self.native_connection.connect_native(add_host=True))
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.setInterval(2)
        self.timer.timeout.connect(self.poll)
        self._narrow = None
        self.adapt_layout()
        self.refresh()
        self.timer.start()

    def poll(self) -> None:
        gestures = self.runtime.tick(time.perf_counter())
        if gestures:
            self.strum.setStyleSheet("color: #f3e3c3;")
            self.flash_timer.start()
        self.refresh()

    def refresh(self) -> None:
        state = self.runtime.snapshot()
        if state == self.previous:
            return
        if self.previous is not None and self.previous.selection.bank != state.selection.bank:
            self.save_timer.start()
        self.previous = state
        self.device_name.setText(state.device.name)
        self.device_status.setText(("● " if state.device.connected else "○ ") + state.device.detail)
        self.faces.set_faces(state.faces, state.fret_set)
        self.set_name.setText(state.fret_set.name)
        self.bank_label.setText(f"Set {state.selection.bank} of 3")
        self.held_frets.setText("Held frets: " + (", ".join(map(str, state.selection.frets)) or "Open"))
        self.bank_pending.setText(f"Set {state.pending_bank} queued · release held buttons" if state.pending_bank else "")
        self.bank_pending.setVisible(state.pending_bank is not None)
        self.harmony.setText(state.harmony.label)
        for widget, string in zip(self.string_labels, state.voicing.strings):
            value = "Muted" if string.note is None else f"{note_name(string.note)} · {'open' if string.fret == 0 else 'fret ' + str(string.fret)}"
            widget.setText(f"{string.string}: {value}")
        if state.midi_ports != tuple(self.midi_port.itemData(i) for i in range(1, self.midi_port.count())):
            self.midi_port.clear()
            self.midi_port.addItem("Not connected", "")
            for name in state.midi_ports:
                self.midi_port.addItem(name, name)
        if self.midi_port.count() == 0:
            self.midi_port.addItem("Not connected", "")
        self.midi_port.setCurrentIndex(max(0, self.midi_port.findData(state.midi_port)))
        self.midi_status.setText(state.midi_status)
        self.lever.set_position(state.lever_x, state.lever_y)
        gesture = state.latest_strum
        if gesture is None:
            self.strum.setText("Waiting for a strum")
            self.fingering.setText("Held at stroke: none")
            self.strum_meta.setText(f"Strums: {state.strum_count}")
        else:
            self.strum.setText(f"{gesture.direction.name}  /  {gesture.character.name}")
            names = ", ".join(map(str, state.latest_selection.frets)) if state.latest_selection else ""
            self.fingering.setText("Frets at stroke: " + (names or "Open"))
            self.strum_meta.setText(f"Strums: {state.strum_count}")
            self.strum_meta.setToolTip(f"Last stroke timestamp: {gesture.timestamp:.6f} s (perf_counter)")
        self.audio_status.setText(state.audio_status)
        self.mute.blockSignals(True)
        self.mute.setChecked(state.muted)
        self.mute.setText("Unmute preview" if state.muted else "Mute preview")
        self.mute.blockSignals(False)
        self.mute.setEnabled(self.runtime.preview.available)

    def change_settle(self, value: float) -> None:
        self.runtime.set_settle_ms(value)
        self.save_timer.start()
        self.refresh()

    def change_bank(self, action: BankAction) -> None:
        self.runtime.bank_action(action)
        self.refresh()

    def open_set_editor(self) -> None:
        # Non-blocking window-modal dialog; input and scheduling timers continue.
        self.editor = FretSetEditor(self.runtime.settings.fret_sets, self.runtime.bank, self)
        self.editor.accepted.connect(self.apply_set_editor)
        self.editor.open()

    def apply_set_editor(self) -> None:
        self.runtime.set_fret_sets(self.editor.result_sets)
        self.save_settings()
        self.refresh()

    def change_midi_channel(self, channel: int) -> None:
        self.runtime.set_midi_channel(channel)
        self.save_timer.start()

    def change_spread(self, value: float) -> None:
        self.runtime.set_spread_ms(value)
        self.save_timer.start()
        self.refresh()

    def refresh_ports(self) -> None:
        self.runtime.midi.refresh(rescan=True)
        self.refresh()

    def connect_port(self, index: int) -> None:
        self.runtime.connect_midi(self.midi_port.itemData(index) or "")
        self.save_timer.start()
        self.refresh()

    def adapt_layout(self) -> None:
        narrow = self.width() < 780
        if narrow == self._narrow:
            return
        self._narrow = narrow
        direction = QBoxLayout.Direction.TopToBottom if narrow else QBoxLayout.Direction.LeftToRight
        self.controls_layout.setDirection(direction)
        self.lower_layout.setDirection(direction)
        self.audio_buttons_layout.setDirection(direction)
        for widget in self.string_labels:
            self.strings_layout.removeWidget(widget)
        columns = 3 if narrow else 6
        for i, widget in enumerate(self.string_labels):
            self.strings_layout.addWidget(widget, i // columns, i % columns)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_narrow"):
            self.adapt_layout()

    def change_volume(self, value: int) -> None:
        self.runtime.set_volume(value / 100)
        self.volume_value.setText(f"{value}%")
        self.save_timer.start()
        self.refresh()

    def change_mute(self, muted: bool) -> None:
        self.runtime.preview.set_muted(muted)
        self.refresh()

    def save_settings(self) -> None:
        self.store.save(self.runtime.settings)
        self.settings_status.setText(self.store.error)
        self.settings_status.setVisible(bool(self.store.error))

    def closeEvent(self, event) -> None:
        if self._closing:
            event.accept()
            return
        self._closing = True
        self.timer.stop()
        self.save_timer.stop()
        self.flash_timer.stop()
        self.native_connection.close()
        self.runtime.close()
        self.runtime.settings.window_geometry = bytes(self.saveGeometry().toBase64()).decode("ascii")
        self.save_settings()
        event.accept()
