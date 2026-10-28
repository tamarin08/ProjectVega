"""Draw Edmond's original glossy wave emblem and export the default MPC map."""

import os
from pathlib import Path
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "src"))
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QApplication
from edmond.engine import midi_map
from edmond.settings import Settings

app = QApplication.instance() or QApplication([])
folder = ROOT / "src" / "edmond" / "resources"
folder.mkdir(parents=True,exist_ok=True)
canvas = QImage(256,256,QImage.Format.Format_ARGB32)
canvas.fill(Qt.GlobalColor.transparent)
p = QPainter(canvas)
p.setRenderHint(QPainter.RenderHint.Antialiasing)
gradient = QLinearGradient(0,0,0,256)
gradient.setColorAt(0,QColor("#ffffff"))
gradient.setColorAt(1,QColor("#8ed4f4"))
p.setBrush(gradient)
p.setPen(QPen(QColor("white"),5))
p.drawEllipse(8,8,240,240)
p.setPen(Qt.PenStyle.NoPen)
p.setBrush(QColor("#e53551"))
p.drawEllipse(84,48,88,88)
p.setPen(QPen(QColor("#419dce"),20,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
p.drawArc(QRectF(48,102,160,86),195*16,150*16)
p.drawArc(QRectF(69,144,118,68),195*16,150*16)
p.setPen(QPen(QColor(255,255,255,190),12,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
p.drawArc(QRectF(36,30,180,174),40*16,100*16)
p.end()
if not canvas.save(str(folder / "edmond.ico")):
    raise RuntimeError("Could not write icon")
canvas.save(str(folder / "edmond.png"))
(folder / "Project Edmond.xmm").write_text(midi_map(Settings()),encoding="utf-8")
print("Generated Edmond icon and default MIDI map")
