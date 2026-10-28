# Vega user guide

Current installation and **Add to FL Studio** setup are described in the
[main README](../README.md). Version 1.0.1 includes native Windows MIDI routing
on updated Windows 11 25H2 or later. No external loopback utility is needed.
The following detailed control and preference reference originated with 1.0.0;
old installer hashes and external-routing instructions are historical.

## Connect Titan

Set the physical switches to **PC + DP**, release the buttons and center the
lever before connecting. Vega waits if the Titan is missing and resumes after
reconnection. LS/RS profiles are not supported. Run one Vega app/diagnostic at a time.
If multiple controllers make selection ambiguous, `Vega.exe --device-index N`
selects the initial device using the index shown in the waiting status.
Vega reads ordinary SDL events and installs no controller driver.

## Playing Vega

- **RIGHT:** low string to high string. **LEFT:** reverse order.
- **DOWN + horizontal:** FULL, all available strings, velocity 110.
- **Vertical center + horizontal:** NORMAL, highest four strings, velocity 90.
- **UP + horizontal:** STRICT, highest three strings, velocity 72.
- Return horizontally to center before another stroke; full center is not needed.
  Vertical-only movements, fret changes and set changes are silent.
- With no buttons held: **E2 A2 D3 G3 B3 E4**.
- Hold several faces to select a harmony. Factory Set 1, buttons 1/5/8, gives
  F major. Unknown combinations remain valid Custom harmonies.

Vega generates a deterministic guitar voicing, not a keyboard chord. Difficult
custom sets may mute strings. The panel shows frets, harmony, strings and last strum.
**Gesture settle** defaults to 8 ms (0–20); **String spread** defaults to 10 ms
(1–30). They are independent. Timing is best-effort, not hard realtime.

Preview starts **muted every launch**. Unmute for triangle tones, not a sampled
guitar. Preview and MIDI share notes, velocity, order and spread. Three preview
strums overlap; a fourth replaces the oldest. Mute affects preview only.
**Panic / Stop** stops both outputs and pending strokes; future strokes can sound.
Audio failure does not disable input or MIDI.

## Fret Sets

Exactly three sets map FACE_1–FACE_8 to frets 1–24:

| Set | Factory name | Frets in physical face order |
| --- | --- | --- |
| 1 | Chromatic | 1, 2, 3, 4, 5, 6, 7, 8 |
| 2 | Major / Dominant | 2, 4, 5, 7, 9, 10, 11, 12 |
| 3 | Minor / Blues | 2, 3, 5, 6, 7, 8, 10, 12 |

**Options** (verified pygame button 7) advances 1 → 2 → 3 → 1, once per press.
GUI Previous/Next do the same. Switching waits for released faces and a finalized
pending stroke; it never reinterprets that stroke.

**Edit Fret Sets...** opens three tabs. Names are labels, not modes. Names allow
40 characters; blanks become “Set N”. Duplicate fret assignments are allowed:
buttons light separately but select a pitch once. No buttons means open guitar;
fret 0 is not an editable slot. Save applies all sets together; an already
settling stroke keeps its captured mapping. Cancel discards edits. Reset This
Set / Reset All Sets are staged until Save. Editing/resetting never sounds.

Settings live at `%LOCALAPPDATA%\ProjectVega\settings.json`: sets, active set,
preview volume, settle/spread, MIDI selection/channel and geometry. Old settings
load without manual deletion. Invalid fields use safe defaults; invalid mapping
data defaults atomically without losing other valid preferences. Unknown
preferences survive. Preview permission is never restored.

## Advanced MIDI / DAW setup

Vega outputs standard MIDI to an **existing Windows output**. It does **not**
create a native “Vega Guitar” virtual endpoint. An external loopback port is
needed only for routing to a DAW on the **same PC**, not for installation or
startup. Hardware MIDI outputs also work with suitable external routing.

1. Enable a loopback cable with an output for Vega and input for the DAW.
   You may name it **Vega Guitar**. Keep the cable running.
2. In Vega click **Refresh**, choose that output, confirm Connected, and leave
   Channel 1 unless your instrument needs another channel.
3. Enable the matching input in the DAW and select/arm an instrument track.
   In FL Studio: **Options → MIDI settings → Input → matching cable → Enable**,
   use **(generic controller)**, then select a loaded instrument channel.
4. Keep preview muted, strum, record notes and inspect timing/release. Test Panic
   and Titan disconnect. Do not route the DAW output back into the same cable.

This is the intended generic workflow, not a claim of completed live DAW testing.
See FL Studio's [MIDI settings documentation](https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/envsettings_midi.htm).
Other DAWs use normal monitored/armed software-instrument routing. Octave labels
differ; compare MIDI numbers: open strings **40, 45, 50, 55, 59, 64**.

Startup prefers exact **Vega Guitar**, then your saved output, never an arbitrary
system synth. Missing selections stay disconnected. “Not connected” disconnects
for the session. Refresh stops MIDI, rescans and reopens the same port if present.
While connected, Windows inventory is checked at most every two seconds;
changes trigger the same safe rescan. Failed ports await Refresh/selection.

Panic sends tracked note-offs and sustain-off/All Notes Off/All Sound Off on the
selected port. Use a dedicated Vega port. Channel changes stop existing notes.
Durations: FULL 800 ms, NORMAL 600 ms, STRICT 350 ms. Same-channel equal pitches
retrigger; an older note-off cannot stop a newer note.

## Troubleshooting

- **No Titan:** check PC + DP and reconnect. Do not change drivers.
- **No MIDI outputs:** normal and nonfatal. Edit sets or use preview; configure
  routing later. Microsoft MIDI Mapper / GS Wavetable Synth are not DAW loopbacks.
- **Port disappeared:** Refresh/reselect. If the driver vanished before receiving
  note-offs, also use the DAW's Panic/All Notes Off.
- **No preview:** explicitly unmute and check volume/audio status. Startup builds
  tones, so allow a few seconds. MIDI is independent.
- **Small screen:** panels stack and scroll; maximizing is optional. Restored
  geometry is clamped to the available screen.
- **Setup refuses a folder:** unrelated files, conflicting shortcuts and redirected
  paths are protected. Use the registered installation or an empty destination.
- **Settings error:** Vega shows a status and continues. Back up JSON before
  repairing it; upgrades do not require deleting custom Fret Sets.

## Development / Building From Source

This section is **for developers**, not installed-app users. Build on Windows
with Python 3.13 x64. Core uses pygame; desktop adds Qt and Mido; tests use
standard-library unittest and the desktop extra; packaging adds PyInstaller.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[desktop,packaging]"
.\.venv\Scripts\Activate.ps1
python -m vega.app
```

Default MIDI uses bundled pygame/PortMidi with Mido encoding. `.[rtmidi]` is an
optional developer alternative; source installation may require C++ tools.
It is not required by the released app.

Install [Inno Setup 6](https://jrsoftware.org/isdl.php) on the **build PC**, then:

```powershell
.\scripts\build-windows.ps1
.\scripts\build-installer.ps1
```

Outputs: `dist\Vega\` and **`dist\installer\Vega-Setup.exe`**. The second script
consumes the first output, with no second application-packaging configuration.
Compiler override: `-Compiler C:\path\ISCC.exe`. First license collection needs
network; notices are cached under ignored `build/license-cache`. A hashed build
inventory rejects missing/changed payloads before Setup compilation. Keep the
entire packaged folder together when testing it. Generated artifacts stay out of Git.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\scripts\smoke-windows.ps1
.\scripts\test-installer.ps1
```

Installer tests use GUID-isolated identity, paths, shortcuts and settings, not
your personal installation. Host tests are not clean-machine tests: follow the
[clean Windows acceptance checklist](CLEAN_WINDOWS_TEST.md) when testing a
new build. Sandbox is a developer testing tool, not an end-user requirement.

Standalone diagnostics remain available:

```powershell
python -m vega.diagnostics.inspect_titan --mode DP --log titan-dp.txt
python -m vega.diagnostics.inspect_gestures --log gestures-8ms.txt
```

Raw discovery can label DP/LS/RS sessions without implying musical support for
LS/RS. Send device metadata, baseline, changed button/axis/hat events and reconnect
lines, with the physical test order. Logs are never overwritten. Gesture inspection
covers horizontal rearming, upper/lower arcs and captured fingering; `--settle-ms N`
changes only that diagnostic run. See [ARCHITECTURE.md](../ARCHITECTURE.md) for boundaries.

## License

Vega uses the [Unlicense](../LICENSE), with no EULA acceptance. Dependencies keep
their licenses. Distributions include [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)
and collected `licenses/` files. Review exact dependency/source obligations before
public distribution.
