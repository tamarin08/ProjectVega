"""Windows identity and resource paths shared by source and frozen builds."""

from pathlib import Path

APP_NAME = "Vega"
APP_DESCRIPTION = "Vega Guitar Controller"
APP_VERSION = "1.0.1"
APP_USER_MODEL_ID = "ProjectVega.Vega"
EXECUTABLE_NAME = "Vega.exe"


def icon_path() -> Path:
    # PyInstaller preserves this package-relative location in its data bundle.
    return Path(__file__).resolve().parent / "resources" / "vega.ico"


def set_windows_identity() -> None:
    import sys

    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)


def use_dark_window_frame(window_id: int) -> None:
    """Best-effort Windows 11 title-bar color; no blur or theme dependency."""
    import sys

    if sys.platform == "win32":
        import ctypes

        enabled = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(window_id), 20, ctypes.byref(enabled), ctypes.sizeof(enabled)
        )
