# Edmond

Windows drum-pad MIDI controller for the **Qanba Titan**, designed for free
**Akai MPC Beats**, including the current MPC 3 Beats application.

[Download Edmond Setup](https://github.com/tamarin08/ProjectEdmond/releases/latest/download/Edmond-Setup.exe) · [Releases](https://github.com/tamarin08/ProjectEdmond/releases)

## Install

Run **Edmond-Setup.exe**, then launch **Project Edmond** from Start.
Updated Windows 11 25H2 or later, x64. Python and the app dependencies are
included; no developer tools are needed. Setup installs per user, without an administrator prompt.
Uninstall through Windows Settings → Apps → Project Edmond. Preferences survive.

Set Titan to **PC + DP**, center the lever and release the faces before connecting.
Close Vega before using Edmond with the same Titan.

## Controls

| Control | Action |
| --- | --- |
| Eight faces | Play the selected group of eight pads |
| Options | Switch between pads 01–08 and 09–16 |
| Lever left / right | Select pads 01–08 / 09–16 |
| Lever up / down | Velocity 127 / 55 |
| Lever centered | Base velocity, initially 100 |
| Note repeat | Repeat held pads at 1/8, 1/16 or 1/32 of local BPM |
| Panic / Stop | Stop repeat, pending hits and active MIDI notes |

Click any onscreen pad to test without a Titan. Default MIDI channel: **10**.
Default pad notes: **36–51**. Pad notes and channel are editable. Repeat starts off
on every launch and uses a local timer; match BPM in Beats. It does not receive
MIDI clock. Titan switches do not measure strike pressure.

## Connect MPC Beats

Click **Add to MPC**. Edmond creates a native Windows MIDI route, selects
**Edmond Drums Send**, installs **Project Edmond.xmm** in Akai's ProgramData MIDI
map library, configures **Edmond Drums** as the host input, and opens MPC.
No loopMIDI utility, extra MIDI driver, SDK download or routing tray app is needed.
All app-side routing and host-setup code is included in Setup. Windows MIDI Service
is part of the supported Windows release and is checked by the installer.

If MPC is already open, Edmond asks you to close it when ready. It then applies
the preferences and reopens MPC without discarding an open project. Existing MIDI
devices and unrelated preferences are preserved; the first preferences edit makes
a `.before-project-edmond` backup beside MPC's settings file.

Load a drum program, select Bank A, and enable monitoring / record arm. The host
makes sound; Edmond supplies notes. If you change Edmond's pad notes or channel,
click Add to MPC again to update the host profile. Export MPC map remains available
for manual or advanced setup.

For an older host or a custom setup, enable Track, Global/Master and Control for
**Edmond Drums** in the host's MIDI preferences and choose the **Project Edmond**
map in its MIDI Learn browser. Use **View → Browser → MIDI Learn Browser** in MPC 3.
Do not send the host's MIDI output back into the same route.

The current free **MPC 3 Beats** uses the MPC 3 application. A loaded instrument
or drum program and a working audio device are still required in the DAW.
The apps do not bundle proprietary DAWs, instruments or sound libraries.

## Compatibility status

Automated controls, settings and host-profile checks pass. Actual Windows MIDI
receipt was verified on both native routes, including matching note-offs.
Physical Titan play and audible DAW output are separate hands-on checks; they are
not claimed as new test passes. See the release verification for the exact scope.

## Preferences and troubleshooting

Preferences: `%LOCALAPPDATA%\ProjectEdmond\settings.json`, separate from Vega.

- No Titan: check PC + DP and reconnect. If several controllers are attached,
  use `Edmond.exe --device-index N` to select the initial device.
- No output: click Add to MPC; check that Windows is updated and Windows MIDI Service is available.
- No sound: check the selected output, matching host input, monitor/arm, drum
  program and pad assignments. Edmond does not contain a synth.
- Cable disconnected: Refresh/reselect. Also use the host's Panic if its driver
  disappeared before Edmond could deliver note-offs.
- Small display: scroll to reach the remaining controls.

## Source and building

Edmond's source and shared Titan/MIDI code are maintained in
[ProjectVega](https://github.com/tamarin08/ProjectVega), under `src/edmond`,
`src/vega/input` and `src/vega/midi`. The ProjectEdmond repository provides the
Edmond download, MIDI map and setup guide. Build from the source repository root:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[desktop,packaging]"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\scripts\build-edmond.ps1 -Compiler C:\path\to\ISCC.exe
```

Use Python 3.13 x64 and Inno Setup 6 on the build PC. Output:
`dist/installer/Edmond-Setup.exe`. End users only need the finished installer.

License: Unlicense; bundled dependencies retain their own terms. E. Honda inspires
the project name and white, baby-blue and red palette. No game assets are included.
