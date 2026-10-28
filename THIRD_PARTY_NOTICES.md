# Distribution notices

Native MIDI routing calls the Windows MIDI Service already installed in supported
Windows 11 releases. Its COM interface identifiers and configuration contract are
referenced from [Microsoft's MIT-licensed MIDI source](https://github.com/microsoft/MIDI/tree/inbox-preview-11).
The notice is included as `licenses/Windows-MIDI-Services.txt`. Microsoft SDK/API
binaries, preview runtimes, drivers and tools are not bundled with this app.

Project Vega source is released under the **Unlicense**, in `LICENSE`.
That does not relicense the third-party components bundled with Vega.
There is no Vega EULA or license-acceptance step in Setup.

The packaged application uses:

| Component | License / source |
| --- | --- |
| CPython and its bundled libraries | PSF and included third-party terms; `licenses/Python-LICENSE.txt`; https://www.python.org/downloads/source/ |
| Qt Core/Gui/Widgets/Network/Svg/OpenGL and image plugins, PySide6, Shiboken | LGPL v3 option, plus embedded third-party notices; https://code.qt.io/cgit/qt/ and https://code.qt.io/cgit/pyside/pyside-setup.git/ |
| pygame | LGPL v2.1; https://github.com/pygame/pygame/tree/2.6.1 |
| SDL2, SDL image/mixer/ttf and codec/font/image dependencies | Individual notices in `licenses/pygame/pygame/2.6.1/docs/licenses/` |
| PortMidi | MIT-style notice in the pygame upstream license collection |
| Mido | MIT; https://github.com/mido/mido |
| packaging | Apache 2.0 / BSD; installed license texts included |
| PyInstaller bootloader | GPL with distribution exception; installed COPYING text included |
| setuptools and vendored support modules | MIT and individual included notices |

The exact installed dependency versions and version-matched source URLs are
recorded in `licenses/SOURCES.json`. The build collects upstream Qt/PySide
LICENSES directories, embedded third-party notices and attribution files, and
pygame's library notices. It retains the upstream texts without changing them.
The upstream license collection may cover optional components not shipped here.
Unused Qt PDF/Virtual Keyboard plugins and their QML dependency tree are excluded
from the payload. Inno Setup is a build tool; its compiler is not included in Vega's payload.

Qt/SDL libraries are dynamically loaded from the ordinary, unpacked `_internal`
directory. You may replace them with ABI-compatible modified builds; Vega adds
no signature checks or restrictions on debugging/reverse engineering for that
purpose. Back up the installation, close Vega, replace the relevant DLLs and
Python extension modules with matching builds, then run Vega.exe. Qt binding,
Qt DLL and Python ABI versions must match. Rebuilding Vega from this repository
with replacement dependencies is also supported by `scripts/build-windows.ps1`.

When distributing binaries, distribute this notice, `LICENSE`, and the complete
`licenses` directory with them. Keep corresponding upstream sources available
as required by their licenses; review the notices for your exact release and
any additional dependencies (including optional RtMidi) before redistribution.
