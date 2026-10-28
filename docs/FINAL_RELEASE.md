# Release verification · October 28, 2026

Release versions: **Vega 1.0.1** and **Edmond 1.0.0**.
Target: updated **Windows 11 25H2 or later, x64**, with Windows MIDI Service.

Both apps have independent per-user Setup installers, shortcuts and settings.
Python, Qt, SDL, MIDI encoding, native routing and host-profile code are included.
The Windows MIDI Service is an operating-system component and is checked by Setup.
No loopMIDI utility, third-party MIDI driver, preview API binary, SDK runtime,
compiler, routing tray app or post-install download is required.

## Checks performed

- Source tests cover Titan controls, voicing/percussion, scheduling, disconnect,
  Panic, settings, UI integration, route ownership, saved external-port retention,
  host-profile preservation, first-run MPC preferences, FL controller callbacks,
  and waiting for a running DAW to close without discarding its project.
- Actual MIDI receipt across the native Windows routes passed. Edmond sent
  notes 36, 44 and 51 on channel 10; Vega sent 40, 45, 50, 55, 59 and 64 on
  channel 1. The DAW-facing inputs received matching note-ons and note-offs.
  Evidence: `build/native-midi-roundtrip.json`.
- Windows MIDI Service's session records confirmed that **MPC 3.exe** and
  **FL64.exe** opened the app-owned native endpoints. The Akai window identified
  itself as **MPC 3 Beats 3.10.0.49**, the free edition.
- Both payloads use complete SHA-256 inventories before installer compilation.
  Packaged native-route checks run with a Windows-only PATH and no source Python.
- GUID-isolated installer scripts verify fresh install, upgrade, native startup,
  shortcuts/registration, uninstall and preservation of personal preferences.
  Vega also checks legacy migration and unsafe-manifest preservation.

Commands:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\scripts\build-windows.ps1
.\scripts\build-installer.ps1
.\scripts\build-edmond.ps1
.\scripts\smoke-windows.ps1
.\scripts\test-installer.ps1
.\scripts\test-edmond-installer.ps1
```

## Host setup

**Add to FL Studio** installs Vega's supportedDevices controller profile, selects
Vega Guitar Send, and opens FL Studio. Notes pass through unchanged to the selected
instrument. The FL script can report attachment and received-note count locally;
no MIDI or status data is sent over a network.

**Add to MPC** installs Edmond's map in Akai's **ProgramData** MIDI-map library,
enables its DAW-facing input in MPC preferences, selects the map, and opens MPC.
The earlier Import command failure was traced to the map-folder workflow; the
button installs the file directly in the documented library instead of using Import.
A first-edit preferences backup is retained. Unrelated devices are preserved.

If a DAW is already running, setup waits for the user to close it, then applies the
profile and reopens it. It never terminates a DAW or discards an unsaved project.
The DAWs and their instruments/content are separate installed products; their
proprietary installers and sound libraries are not redistributed.

## Validation limits

Native MIDI receipt and host endpoint connections are verified. Fresh physical
Titan play, audible DAW output, recording latency and automatic profile selection
inside the final DAW UI were not independently confirmed. Desktop input/capture
became unavailable during the live checks. These are not counted as test passes.
The software uses a best-effort desktop timer; it does not promise hard realtime.
Repeat uses local BPM, not incoming MIDI clock.

Earlier Vega 1.0.0 owner-reported physical and FL Studio acceptance remains in
[historical verification](RELEASE_INTEGRATION.md), separate from the current binary.

## Distribution

The shared source is in ProjectVega. ProjectEdmond is its product download and
setup repository and points to the same source. New releases use new tags;
Vega 1.0.0 history is retained. Each release includes its Setup EXE and a
SHA256SUMS.txt file. Edmond also includes its default MIDI map. Uploaded asset
sizes and SHA-256 hashes are checked against the local files. Build fixtures,
credentials and generated executables are excluded from source control.
