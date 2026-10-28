"""Launch Project Edmond: python -m edmond."""

import argparse
import json
import os
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device-index",type=int)
    parser.add_argument("--smoke-report",type=Path,help=argparse.SUPPRESS)
    parser.add_argument("--screenshot",type=Path,help=argparse.SUPPRESS)
    parser.add_argument("--native-midi-report",type=Path,help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.native_midi_report:
        from vega.midi.diagnostics import write_native_report
        from vega.midi.native_route import EDMOND_ROUTE
        return write_native_report(args.native_midi_report,EDMOND_ROUTE)
    os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
    from PySide6.QtCore import QCoreApplication, QEvent, QTimer
    from PySide6.QtGui import QFontDatabase, QIcon
    from PySide6.QtWidgets import QApplication
    from edmond.engine import EdmondEngine
    from edmond import __version__
    from edmond.settings import Settings, SettingsStore
    from edmond.window import EdmondWindow
    from vega.input.desktop_source import DesktopInputSource

    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ProjectEdmond.Edmond")
    app = QApplication(sys.argv[:1])
    if app.platformName() == "offscreen" and sys.platform == "win32":
        # Qt's offscreen platform does not discover the Windows font catalog.
        fonts = Path(os.environ.get("SystemRoot", "C:/Windows")) / "Fonts"
        for name in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf"):
            QFontDatabase.addApplicationFont(str(fonts / name))
    app.setApplicationName("Project Edmond")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("ProjectEdmond")
    app.setWindowIcon(QIcon(str(Path(__file__).parent / "resources" / "edmond.ico")))
    # Smoke mode never reads/writes personal settings or opens a hardware/MIDI port.
    class SmokeStore:
        status = ""
        def save(self,settings): return True
    store = SmokeStore() if args.smoke_report else SettingsStore()
    settings = Settings() if args.smoke_report else store.load()
    engine = EdmondEngine(settings)
    source = None if args.smoke_report else DesktopInputSource(device_index=args.device_index)
    window = None
    try:
        if not args.smoke_report:
            engine.midi.restore(settings.midi_port,prefer_default=False)
        window = EdmondWindow(engine,store,source)
        available = app.primaryScreen().availableGeometry()
        if args.smoke_report:
            window.resize(1120,900)
        else:
            window.resize(min(1120,available.width()-40),min(850,available.height()-40))
        window.show()
        if not args.smoke_report and settings.midi_port in ("", "Edmond Drums Send"):
            QTimer.singleShot(0,window.native_connection.connect_native)
        if args.smoke_report:
            def finish():
                try:
                    report = {"app":"Project Edmond","version":__version__,"pads":len(window.pads),
                              "channel":engine.midi.channel,"notes":settings.notes,"repeat":engine.repeat,
                              "midi_status":engine.midi.status,"settings_isolated":True,
                              "frozen":bool(getattr(sys,"frozen",False)),"icon_present":not app.windowIcon().isNull(),
                              "gui_initialized":window.isVisible()}
                    if args.screenshot:
                        if not window.centralWidget().widget().grab().save(str(args.screenshot)):
                            raise OSError("Screenshot could not be saved")
                    with args.smoke_report.open("x",encoding="utf-8") as stream:
                        json.dump(report,stream,indent=2)
                except Exception as exc:
                    print(str(exc),file=sys.stderr)
                    app.exit(1)
                else:
                    window.close()
                    app.exit(0)
            QTimer.singleShot(600,finish)
        return app.exec()
    finally:
        engine.close()
        if source:
            source.close()
        if window:
            window.close()
            window.deleteLater()
            QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)


if __name__ == "__main__":
    raise SystemExit(main())
