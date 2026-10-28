"""Launch with python -m vega.app. Preview always starts muted."""

import argparse
import sys
import time
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device-index", type=int, help="Initial Titan index if multiple controllers are attached")
    parser.add_argument("--smoke-test-report", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--smoke-test-settings", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--smoke-test-edit-set", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--native-midi-report", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.native_midi_report:
        from vega.midi.diagnostics import write_native_report
        from vega.midi.native_route import VEGA_ROUTE
        return write_native_report(args.native_midi_report, VEGA_ROUTE)
    if (args.smoke_test_settings or args.smoke_test_edit_set) and not args.smoke_test_report:
        parser.error("Smoke settings/edit flags require --smoke-test-report")
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        message = f"Vega could not load its desktop dependencies: {exc}"
        if args.smoke_test_report:
            import json

            with args.smoke_test_report.open("x", encoding="utf-8") as report:
                json.dump({"error": message}, report)
        elif sys.stderr is None and sys.platform == "win32":
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, message, "Vega", 0x10)
        else:
            print(message, file=sys.stderr)
            print('Install desktop dependencies: python -m pip install -e ".[desktop]"', file=sys.stderr)
        return 2

    from vega.app.window import VegaWindow
    from vega.app.identity import APP_NAME, APP_VERSION, icon_path, set_windows_identity, use_dark_window_frame
    from PySide6.QtGui import QIcon
    from vega.audio.preview import PreviewSynth
    from vega.audio.pygame_backend import PygameAudioBackend
    from vega.input.desktop_source import DesktopInputSource
    from vega.runtime import VegaRuntime
    from vega.settings import SettingsStore

    set_windows_identity()
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setWindowIcon(QIcon(str(icon_path())))
    app.setStyle("windowsvista")
    app.setOrganizationName("ProjectVega")
    store = SettingsStore()
    if args.smoke_test_report:
        from vega.app.smoke import SmokeSettingsStore

        store = SettingsStore(args.smoke_test_settings) if args.smoke_test_settings else SmokeSettingsStore()
    settings = store.load()
    preview = PreviewSynth(PygameAudioBackend(), settings.preview_volume)
    runtime = VegaRuntime(DesktopInputSource(device_index=args.device_index), preview, settings,
                          clock=time.perf_counter)
    from vega.midi.native_route import VEGA_ROUTE
    runtime.midi.default_port = VEGA_ROUTE.send_name
    window = None
    try:
        runtime.midi.restore(settings.midi_port, prefer_default=False)
        window = VegaWindow(runtime, store)
        window.show()
        if not args.smoke_test_report and settings.midi_port in ("", VEGA_ROUTE.send_name):
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, window.native_connection.connect_native)
        if app.platformName() == "windows":
            use_dark_window_frame(int(window.winId()))
        if args.smoke_test_report:
            from PySide6.QtCore import QTimer
            from vega.app.smoke import write_report

            def finish_smoke_test():
                result = 0
                try:
                    if args.smoke_test_edit_set:
                        window.open_set_editor()
                        window.editor.names[0].setText("Release verification")
                        window.editor.slots[0][0].setValue(24)
                        window.editor.accept()
                    write_report(window, args.smoke_test_report)
                except OSError:
                    result = 1
                finally:
                    window.close()
                    app.exit(result)

            QTimer.singleShot(1000, finish_smoke_test)
        return app.exec()
    finally:
        runtime.close()
        if window is not None:
            from PySide6.QtCore import QCoreApplication, QEvent
            window.close()
            window.deleteLater()
            # exec() has ended: explicitly drain deferred deletions before
            # QApplication/Python tear down native Qt objects in arbitrary order.
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


if __name__ == "__main__":
    raise SystemExit(main())
