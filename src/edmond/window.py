"""Glossy aqua desktop surface for Edmond; all performance logic lives in engine."""

from pathlib import Path
import time

from PySide6.QtCore import Qt, QTimer, QRectF, QSize
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton,
    QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from edmond.engine import EdmondEngine, midi_map
from edmond.settings import valid_notes

STYLE = """
QWidget { color: #19435b; font-family: 'Segoe UI'; font-size: 13px; }
QLabel { background: transparent; }
QFrame#panel { background: rgba(255,255,255,225); border: 1px solid white; border-radius: 23px; }
QLabel#eyebrow { color: #c82d44; font-weight: 700; font-size: 11px; letter-spacing: 3px; }
QLabel#title { font-size: 46px; font-weight: 700; color: #164b70; }
QLabel#heading { font-size: 18px; font-weight: 700; color: #235878; }
QLabel#muted { color: #5a8196; font-size: 12px; }
QPushButton { border: 1px solid #a6d7ea; border-radius: 13px; padding: 10px 15px;
 background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 white,stop:0.48 #f3fcff,stop:1 #d2edfa); font-weight: 600; }
QPushButton:hover { border: 1px solid #56acda; background: #e8faff; }
QPushButton:pressed, QPushButton:checked { background: #b4e4fa; border-color: #71c1e5; }
QPushButton#red { color: white; border: 1px solid #bb2641;
 background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #f78997,stop:0.48 #e84e66,stop:0.5 #d92e4e,stop:1 #bd173b); }
QPushButton#red:checked { background: #a91433; }
QComboBox, QSpinBox { background: #f5fcff; border: 1px solid #b9ddea; border-radius: 9px; padding: 7px; min-height: 22px; }
QComboBox::drop-down { border: none; width: 22px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #e2f4fb; width: 10px; }
QScrollBar::handle:vertical { background: #a4d7eb; border-radius: 5px; min-height: 30px; }
QToolTip { background: white; border: 1px solid #b2dbed; padding: 7px; }
"""


def label(text, name=None):
    widget = QLabel(text)
    widget.setWordWrap(True)
    if name:
        widget.setObjectName(name)
    return widget


class AquaSurface(QWidget):
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0, QColor("#f2fcff"))
        gradient.setColorAt(.45, QColor("#c5eafb"))
        gradient.setColorAt(1, QColor("#86cbe9"))
        painter.fillRect(self.rect(), gradient)
        for fx, fy, radius in ((.93,.05,145),(.07,.46,90),(.94,.83,200),(.72,.20,36),(.4,.96,65)):
            x, y = self.width()*fx, self.height()*fy
            orb = QRadialGradient(x-radius*.3, y-radius*.4, radius*1.6)
            orb.setColorAt(0, QColor(255,255,255,175))
            orb.setColorAt(.55, QColor(255,255,255,18))
            orb.setColorAt(1, QColor(255,255,255,90))
            painter.setBrush(orb)
            painter.setPen(QPen(QColor(255,255,255,155), 1.5))
            painter.drawEllipse(QRectF(x-radius,y-radius,radius*2,radius*2))


class Emblem(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(86, 86)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor("white"), 2))
        gradient = QLinearGradient(0,0,0,86)
        gradient.setColorAt(0,QColor("#ffffff"))
        gradient.setColorAt(1,QColor("#a8dff7"))
        p.setBrush(gradient)
        p.drawEllipse(3,3,80,80)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#df3551"))
        p.drawEllipse(28,16,30,30)
        p.setPen(QPen(QColor("#46a5d4"), 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(QRectF(16,34,54,29), 195*16,150*16)
        p.drawArc(QRectF(23,48,40,23), 195*16,150*16)
        p.setPen(QPen(QColor(255,255,255,180), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(QRectF(12,10,60,58), 40*16,100*16)


class GlossPad(QPushButton):
    def __init__(self, pad):
        super().__init__()
        self.pad = pad
        self.note = 36 + pad
        self.face = ""
        self.lit = False
        self.setMinimumSize(108, 100)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self):
        return QSize(138, 116)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(4, 3, -4, -7)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(36,105,148,35))
        p.drawRoundedRect(rect.translated(0,4), 23,23)
        gradient = QLinearGradient(0,rect.top(),0,rect.bottom())
        colors = ("#ffb9c0", "#ed6a80", "#cb3154") if self.lit or self.isDown() else (
            ("#ffffff", "#bee9fb", "#7cc4e7") if self.face else ("#f8fdff", "#e0f3fb", "#bfdeee"))
        for position, color in zip((0,.5,1), colors):
            gradient.setColorAt(position,QColor(color))
        p.setBrush(gradient)
        p.setPen(QPen(QColor("white"),1.5))
        p.drawRoundedRect(rect,23,23)
        p.setPen(Qt.PenStyle.NoPen)
        gloss = QLinearGradient(0,rect.top(),0,rect.center().y())
        gloss.setColorAt(0,QColor(255,255,255,195))
        gloss.setColorAt(1,QColor(255,255,255,12))
        p.setBrush(gloss)
        p.drawRoundedRect(QRectF(rect.left()+5,rect.top()+4,rect.width()-10,rect.height()*.44),19,19)
        p.setPen(QColor("#8f1b38") if self.lit else QColor("#164e70"))
        p.setFont(QFont("Segoe UI",23,QFont.Weight.Bold))
        p.drawText(rect.adjusted(15,9,-9,-25),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,f"{self.pad+1:02}")
        p.setFont(QFont("Segoe UI",9,QFont.Weight.DemiBold))
        p.drawText(rect.adjusted(16,0,-12,-12),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignBottom,self.face or "CLICK TO PLAY")
        p.setFont(QFont("Segoe UI",9))
        p.drawText(rect.adjusted(0,9,-13,0),Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTop,str(self.note))


class NoteEditor(QDialog):
    def __init__(self, settings, parent):
        super().__init__(parent)
        self.setWindowTitle("Edmond · Pad notes")
        self.setStyleSheet(STYLE)
        layout = QVBoxLayout(self)
        layout.addWidget(label("Assign sixteen distinct MIDI notes (0–127). Export a new MPC map after changing notes or channel."))
        grid = QGridLayout()
        self.slots = []
        for index, note in enumerate(settings.notes):
            spin = QSpinBox()
            spin.setRange(0,127)
            spin.setValue(note)
            self.slots.append(spin)
            row, col = index%8,index//8*2
            grid.addWidget(QLabel(f"A{index+1:02}"),row,col)
            grid.addWidget(spin,row,col+1)
        layout.addLayout(grid)
        reset = QPushButton("Chromatic 36–51")
        reset.clicked.connect(lambda: [spin.setValue(36+i) for i,spin in enumerate(self.slots)])
        layout.addWidget(reset)
        self.error = label("")
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        if not valid_notes(tuple(spin.value() for spin in self.slots)):
            self.error.setText("Each pad needs a different MIDI note.")
            return
        super().accept()


class EdmondWindow(QMainWindow):
    def __init__(self, engine: EdmondEngine, store, source=None):
        super().__init__()
        self.engine, self.store, self.source = engine, store, source
        self._closing = False
        self.setWindowTitle("Project Edmond · MPC Beats Controller")
        self.resize(1120, 850)
        self.setStyleSheet(STYLE)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.setCentralWidget(scroll)
        surface = AquaSurface()
        surface.setMinimumWidth(790)
        scroll.setWidget(surface)
        layout = QVBoxLayout(surface)
        layout.setContentsMargins(32,26,32,24)
        layout.setSpacing(19)
        header = QHBoxLayout()
        header.addWidget(Emblem())
        title = QVBoxLayout()
        title.setSpacing(0)
        title.addWidget(label("MIDI CONTROLLER", "eyebrow"))
        title.addWidget(label("Edmond", "title"))
        title.addWidget(label("Titan drum controller for MPC Beats", "muted"))
        header.addLayout(title)
        header.addStretch()
        help_button = QPushButton("Connect to MPC Beats")
        help_button.clicked.connect(self.show_help)
        header.addWidget(help_button,alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)
        self.device_label = label("")
        layout.addWidget(self.device_label)
        content = QHBoxLayout()
        content.setSpacing(20)
        left, controls = self.panel()
        left.setFixedWidth(260)
        controls.addWidget(label("MIDI", "eyebrow"))
        controls.addWidget(label("Output", "heading"))
        controls.addWidget(label("MIDI output", "muted"))
        self.port = QComboBox()
        self.port.setMinimumWidth(0)
        self.port.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.port.setMinimumContentsLength(16)
        self.port.activated.connect(self.select_port)
        controls.addWidget(self.port)
        refresh = QPushButton("Refresh outputs")
        refresh.clicked.connect(self.refresh_ports)
        controls.addWidget(refresh)
        self.midi_status = label("", "muted")
        self.midi_status.setTextFormat(Qt.TextFormat.PlainText)
        controls.addWidget(self.midi_status)
        self.add_mpc = QPushButton("Add to MPC")
        controls.addWidget(self.add_mpc)
        self.daw_status = label("Built-in MIDI routing · no separate loopback utility", "muted")
        controls.addWidget(self.daw_status)
        form = QFormLayout()
        self.channel = self.spin(1,16,engine.settings.channel)
        self.channel.valueChanged.connect(self.set_channel)
        form.addRow("Channel", self.channel)
        self.velocity = self.spin(1,127,engine.settings.velocity)
        self.velocity.valueChanged.connect(lambda n:setattr(engine.settings,"velocity",n))
        form.addRow("Base velocity", self.velocity)
        controls.addLayout(form)
        controls.addSpacing(8)
        controls.addWidget(label("NOTE REPEAT", "eyebrow"))
        self.repeat = QPushButton("Note repeat · OFF")
        self.repeat.setObjectName("red")
        self.repeat.setCheckable(True)
        self.repeat.toggled.connect(self.set_repeat)
        controls.addWidget(self.repeat)
        repeat_form = QFormLayout()
        self.bpm = self.spin(30,300,engine.settings.bpm)
        self.bpm.valueChanged.connect(lambda n:setattr(engine.settings,"bpm",n))
        repeat_form.addRow("Tempo / BPM",self.bpm)
        self.rate = QComboBox()
        self.rate.addItems(["1/8","1/16","1/32"])
        self.rate.setCurrentIndex((8,16,32).index(engine.settings.division))
        self.rate.currentIndexChanged.connect(lambda i:setattr(engine.settings,"division",(8,16,32)[i]))
        repeat_form.addRow("Repeat rate",self.rate)
        controls.addLayout(repeat_form)
        controls.addWidget(label("Hold a face button or a pad. Local tempo: match BPM in Beats; repeat is not MIDI-clock synced.","muted"))
        controls.addStretch()
        stop = QPushButton("■  Panic / Stop")
        stop.setObjectName("red")
        stop.clicked.connect(self.panic)
        controls.addWidget(stop)
        content.addWidget(left)
        right, pads_layout = self.panel()
        pads_header = QHBoxLayout()
        pads_header.addWidget(label("PADS A01–A16", "eyebrow"))
        pads_header.addStretch()
        self.bank_buttons = []
        for bank,text in enumerate(("01–08", "09–16")):
            button = QPushButton(text)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False,b=bank:self.change_bank(b))
            self.bank_buttons.append(button)
            pads_header.addWidget(button)
        pads_layout.addLayout(pads_header)
        grid = QGridLayout()
        grid.setSpacing(6)
        self.pads = []
        for pad in range(16):
            button = GlossPad(pad)
            button.setAccessibleName(f"Pad A{pad+1:02}")
            button.pressed.connect(lambda p=pad:engine.press(f"mouse-{p}",p,time.perf_counter()))
            button.released.connect(lambda p=pad:engine.release(f"mouse-{p}"))
            self.pads.append(button)
            grid.addWidget(button,3-pad//4,pad%4)
        pads_layout.addLayout(grid)
        self.performance = label("", "muted")
        pads_layout.addWidget(self.performance)
        pad_actions = QHBoxLayout()
        edit = QPushButton("Pad notes…")
        edit.clicked.connect(self.edit_notes)
        export = QPushButton("Export MPC map…")
        export.clicked.connect(self.export_map)
        pad_actions.addWidget(edit)
        pad_actions.addWidget(export)
        pads_layout.addLayout(pad_actions)
        content.addWidget(right,1)
        layout.addLayout(content,1)
        footer, footer_layout = self.panel()
        footer_layout.setContentsMargins(18,14,18,14)
        footer_layout.addWidget(label("LEVER  ←  PADS 01–08     →  PADS 09–16     ↑  ACCENT 127     ↓  GHOST 55     ·     OPTIONS  SWITCH BANK", "muted"))
        footer_layout.addWidget(label("Titan: PC + DP  ·  Click any pad to test MIDI  ·  Sound comes from your instrument in MPC Beats", "muted"))
        layout.addWidget(footer)
        self.save_status = label(store.status,"muted")
        layout.addWidget(self.save_status)
        from vega.app.daw_connection import DawConnection
        from vega.midi.native_route import EDMOND_ROUTE
        def apply_native_port(name):
            engine.midi.select(name)
            engine.settings.midi_port = name
        self.native_connection = DawConnection(self, engine.midi, "mpc", apply_native_port,
                                                engine.stop, self.save,
                                                lambda: midi_map(engine.settings, EDMOND_ROUTE.host_name))
        self.native_connection.status_changed.connect(self.daw_status.setText)
        self.add_mpc.clicked.connect(lambda: self.native_connection.connect_native(add_host=True))
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.setInterval(4)
        self.timer.timeout.connect(self.tick)
        self.timer.start()
        self.ui_tick = 0
        self.sync_ports()
        self.render_state(time.perf_counter())

    @staticmethod
    def panel():
        frame = QFrame()
        frame.setObjectName("panel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18,18,18,18)
        layout.setSpacing(12)
        return frame, layout

    @staticmethod
    def spin(low, high, value):
        spin = QSpinBox()
        spin.setRange(low,high)
        spin.setValue(value)
        return spin

    def tick(self):
        now = time.perf_counter()
        if self.source:
            for event in self.source.poll(now):
                self.engine.receive(event,now)
        connected = self.engine.midi.port_name
        self.engine.tick(now)
        if connected and not self.engine.midi.port_name:
            self.engine.stop()
        self.ui_tick += 1
        if self.ui_tick % 8 == 0:
            self.render_state(now)

    def render_state(self, now):
        e = self.engine
        self.device_label.setText(f"●  {e.device.name}  ·  {e.device.detail}")
        self.device_label.setTextFormat(Qt.TextFormat.PlainText)
        self.midi_status.setText(e.midi.status)
        inventory = tuple(self.port.itemData(i) for i in range(1,self.port.count()))
        if inventory != e.midi.port_names or self.port.currentData() != e.midi.port_name:
            self.sync_ports()
        for bank,button in enumerate(self.bank_buttons):
            button.setChecked(bank==e.settings.bank)
        for pad,button in enumerate(self.pads):
            button.note = e.settings.notes[pad]
            button.face = f"FACE {pad%8+1}" if pad//8 == e.settings.bank else ""
            button.lit = e.lit_until.get(pad,0)>now
            button.setToolTip(f"Pad A{pad+1:02} · MIDI note {button.note} · channel {e.settings.channel}")
            button.update()
        last = f"Last A{e.last_hit[0]+1:02} / velocity {e.last_hit[1]}" if e.last_hit else "Last hit: none"
        self.performance.setText(f"{last}    ·    {e.hit_count} hits    ·    Velocity {e.velocity}")

    def sync_ports(self):
        self.port.clear()
        self.port.addItem("Not connected", "")
        for name in self.engine.midi.port_names:
            self.port.addItem(name,name)
        self.port.setCurrentIndex(max(0,self.port.findData(self.engine.midi.port_name)))

    def select_port(self,index):
        self.engine.stop()
        name = self.port.itemData(index) or ""
        self.engine.settings.midi_port = name
        self.engine.midi.select(name)
        self.save()
        self.render_state(time.perf_counter())

    def refresh_ports(self):
        self.engine.stop()
        self.engine.midi.refresh(rescan=True)
        self.render_state(time.perf_counter())

    def set_channel(self,channel):
        self.engine.stop()
        self.engine.midi.set_channel(channel)
        self.engine.settings.channel = channel

    def set_repeat(self,enabled):
        self.engine.set_repeat(enabled,time.perf_counter())
        self.repeat.setText(f"Note repeat · {'ON' if enabled else 'OFF'}")

    def change_bank(self,bank):
        self.engine.set_bank(bank)
        self.render_state(time.perf_counter())

    def panic(self):
        self.engine.stop()
        self.repeat.setChecked(False)
        self.render_state(time.perf_counter())

    def save(self):
        self.store.save(self.engine.settings)
        self.save_status.setText(self.store.status)

    def edit_notes(self):
        self.panic()
        dialog = NoteEditor(self.engine.settings,self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.engine.settings.notes = tuple(spin.value() for spin in dialog.slots)
            self.save()
            self.render_state(time.perf_counter())

    def export_map(self):
        self.panic()
        path,_ = QFileDialog.getSaveFileName(self,"Export Edmond MIDI map","Project Edmond.xmm","MPC MIDI map (*.xmm)")
        if path:
            try:
                Path(path).write_text(midi_map(self.engine.settings,self.engine.settings.midi_port or "Edmond Drums"),encoding="utf-8")
            except OSError as exc:
                QMessageBox.warning(self,"Export failed",str(exc))

    def show_help(self):
        QMessageBox.information(self,"Edmond → MPC Beats",
            "1. Click Add to MPC. Edmond creates its Windows MIDI route, selects Edmond Drums Send, "
            "installs its pad map and configures the host input while MPC is closed.\n\n"
            "2. MPC opens automatically. If it was already running, restart MPC once to load the new profile. "
            "No loopMIDI utility or separate driver is needed.\n\n"
            "3. In MPC Beats: Edit → Preferences → MIDI / Sync. Enable Track and Master (or Global) for that input; enable Control to use MIDI Learn.\n\n"
            "4. Load a drum program on a drum track. Choose the cable as its input, channel 10 (or All), and enable monitoring / record arm.\n\n"
            "5. Export MPC map… then open View → Browser → MIDI Learn Browser in MPC 3 Beats "
            "(Ctrl+Shift+L in older Beats). Import the .xmm from the panel menu. "
            "Default notes are 36–51. Alternatively learn each pad manually using Edmond's clickable pads. "
            "If import reports Unable to copy the file, create a New MIDI Map and Learn its Pad 1–16 targets manually. "
            "Export a new map after changing notes, channel or cable name.\n\n"
            "6. Tap pads, check note recording and both banks, then test Panic and unplug Titan during repeat. "
            "Keep the DAW's output off this cable to avoid a MIDI loop.\n\n"
            "Repeat uses a local timer; match BPM in Beats. Titan buttons are switches, so velocity comes from the lever. "
            "Edmond supplies MIDI; MPC Beats supplies sound. Select Bank A in Beats and check the routing before playing.")

    def closeEvent(self,event):
        if self._closing:
            event.accept()
            return
        self._closing = True
        self.timer.stop()
        self.native_connection.close()
        self.engine.close()
        if self.source:
            self.source.close()
        self.save()
        event.accept()
