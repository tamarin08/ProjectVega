# Vega

Windows MIDI guitar controller for the **Qanba Titan** arcade stick.
Eight buttons choose frets; the lever strums a generated six-string voicing.

[Download Vega Setup](https://github.com/tamarin08/ProjectVega/releases/latest/download/Vega-Setup.exe) · [Releases](https://github.com/tamarin08/ProjectVega/releases) · [User guide](docs/VEGA.md)

## Install

1. Download **Vega-Setup.exe** and run it.
2. Launch **Vega** from the Start Menu.
3. Set Titan to **PC + DP**, release the buttons and center the lever before connecting.

Updated Windows 11 25H2 or later, x64. Setup includes the application and its runtime; Python and build
tools are not needed. Installation is per user, without an administrator prompt.
Reinstall to upgrade. Uninstall through Windows Settings → Apps → Vega.
Custom preferences survive upgrades and uninstall.

## Controls

| Control | Action |
| --- | --- |
| Eight faces | Select frets from one of three editable Fret Sets |
| Right / Left | Strum low-to-high / high-to-low |
| Down + horizontal | Full strum, velocity 110 |
| Center + horizontal | Normal strum, velocity 90 |
| Up + horizontal | Strict strum, velocity 72 |
| Options | Next Fret Set |
| Panic / Stop | Stop notes and pending strokes |

Preview starts muted. Unmute for basic triangle tones, or route MIDI to your DAW
and load a guitar instrument. The [user guide](docs/VEGA.md) covers voicing,
Fret Sets, timing, settings and troubleshooting.

## Connect a DAW

Click **Add to FL Studio**. Vega creates its native Windows MIDI route, selects
**Vega Guitar Send**, installs the FL controller profile, and opens FL Studio.
Select a guitar instrument in FL; Vega supplies MIDI, and the instrument supplies
sound. No loopMIDI utility, driver download or separate routing process is needed.

If FL Studio is already open, Vega asks you to close it when ready, then finishes
setup and reopens it. It never discards an open project. Advanced users can still
choose another existing hardware or software MIDI output.

No Titan, DAW or MIDI port is required to install or launch the app.

## Edmond

[Project Edmond](https://github.com/tamarin08/ProjectEdmond) is the separate drum-pad
controller for free Akai MPC Beats. It has its own installer, shortcuts and settings.
The two apps share the Titan input and MIDI transport code in this repository.
Close one controller app before using the other with the Titan.

## Development / Building From Source

Use Python 3.13 x64 and Inno Setup 6 on Windows:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[desktop,packaging]"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\scripts\build-windows.ps1
.\scripts\build-installer.ps1
```

Vega output: `dist/installer/Vega-Setup.exe`. For Edmond, run
`scripts/build-edmond.ps1`; output: `dist/installer/Edmond-Setup.exe`.
`python -m vega.app` and `python -m edmond` launch the source apps.

[Architecture](ARCHITECTURE.md) · [Release verification](docs/FINAL_RELEASE.md) · [License](LICENSE) · [Dependency notices](THIRD_PARTY_NOTICES.md)
