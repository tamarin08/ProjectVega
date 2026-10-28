"""Install only our host profiles; preserve DAW projects and unrelated preferences."""

from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

from vega.midi.native_route import EDMOND_ROUTE, endpoint_ids

FL_SCRIPT = '''# name=Vega Guitar
# supportedDevices=Vega Guitar
# ProjectVega managed controller profile, version 2

import json
import os
import time

_count = 0
_last_report = 0
_online = False

def _report():
    global _last_report
    _last_report = time.time()
    try:
        folder = os.path.join(os.environ['LOCALAPPDATA'], 'ProjectVega')
        os.makedirs(folder, exist_ok=True)
        target = os.path.join(folder, 'fl-connection.json')
        temporary = target + '.tmp'
        with open(temporary, 'w') as stream:
            json.dump({'app': 'ProjectVega', 'online': _online, 'pid': os.getpid(),
                       'time': _last_report, 'note_on_count': _count}, stream)
        os.replace(temporary, target)
    except (OSError, KeyError):
        pass

def OnInit():
    global _online
    _online = True
    _report()

def OnDeInit():
    global _online
    _online = False
    _report()

def OnIdle():
    if time.time() - _last_report >= 1:
        _report()

def OnMidiMsg(event):
    global _count
    if (getattr(event, 'status', 0) & 0xf0) == 0x90 and getattr(event, 'data2', 0) > 0:
        _count += 1
    # Notes, velocities and controllers go to FL's selected instrument unchanged.
    event.handled = False
'''


def documents_folder() -> Path:
    if sys.platform != "win32":
        return Path.home() / "Documents"
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                       r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as key:
        return Path(os.path.expandvars(winreg.QueryValueEx(key, "Personal")[0]))


def host_executable(host: str) -> Path | None:
    roots = [Path(os.environ.get("ProgramFiles", "C:/Program Files")),
             Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))]
    candidates = []
    for root in roots:
        if host == "mpc":
            candidates += [root / "Akai Pro" / app / (app + ".exe")
                           for app in ("MPC 3", "MPC Beats", "MPC")]
        elif host == "fl":
            candidates += sorted((root / "Image-Line").glob("FL Studio*/FL64.exe"), reverse=True)
    return next((path for path in candidates if path.is_file()), None)


def process_running(executable: Path) -> bool:
    if sys.platform != "win32":
        return False
    # Query process names only. Do not touch or terminate a user's DAW process.
    result = subprocess.run([str(Path(os.environ["SystemRoot"]) / "System32/tasklist.exe"),
                             "/FI", "IMAGENAME eq " + executable.name, "/FO", "CSV", "/NH"],
                            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=5)
    return ('"' + executable.name.casefold() + '"') in result.stdout.casefold()


def managed_write(path: Path, content: str, marker: str) -> None:
    if path.exists():
        old = path.read_text(encoding="utf-8-sig")
        if old == content:
            return
        if marker not in old:
            raise OSError(f"Preserving an existing user file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def install_fl_profile(documents: Path | None = None) -> Path:
    root = documents or documents_folder()
    path = root / "Image-Line/FL Studio/Settings/Hardware/Project Vega/device_Vega.py"
    managed_write(path, FL_SCRIPT, "# ProjectVega managed controller profile")
    return path


def configure_mpc_preferences(path: Path, profile: Path, *, route_ids: dict | None = None) -> bool:
    """Call only while MPC is closed. Change our input entries and selected map."""
    original = path.read_bytes() if path.is_file() else None
    root = ET.fromstring(original) if original is not None else ET.Element("PROPERTIES")
    entries = {node.get("name"): node for node in root.findall("VALUE")}
    table_node = entries.get("MidiDevices.Table")
    table = json.loads(table_node.get("val", "{}")) if table_node is not None else {"value0": []}
    if not isinstance(table, dict) or not isinstance(table.get("value0"), list):
        raise ValueError("MPC's MIDI device table has an unsupported format; preferences were preserved")
    ids = route_ids or endpoint_ids(EDMOND_ROUTE)
    devices = table["value0"]
    for name, key in ((EDMOND_ROUTE.host_name, "endpointB"), (EDMOND_ROUTE.send_name, "endpointA")):
        device = next((item for item in devices if item.get("type") == 0
                       and item.get("deviceId", "").casefold() == ids[key].casefold()), None)
        if device is None:
            device = {"type": 0, "deviceName": name, "deviceId": ids[key], "displayName": name,
                      "connected": True, "sync": False, "ignoreAuto": False, "mpe": False, "ignoreAutoMPE": False}
            devices.append(device)
        device["track"] = name == EDMOND_ROUTE.host_name
        device["global"] = name == EDMOND_ROUTE.host_name
        device["control"] = name == EDMOND_ROUTE.host_name
    values = {"MidiDevices.Table": json.dumps(table), "MidiLearnPreviousMapping": str(profile)}
    for name, value in values.items():
        node = entries.get(name)
        if node is None:
            node = ET.SubElement(root, "VALUE", name=name)
        node.set("val", value)
    backup = path.with_name(path.name + ".before-project-edmond")
    path.parent.mkdir(parents=True, exist_ok=True)
    if original is not None and not backup.exists():
        with backup.open("xb") as stream:
            stream.write(original)
    temporary = path.with_name(path.name + ".edmond-" + uuid.uuid4().hex + ".tmp")
    try:
        ET.ElementTree(root).write(temporary, encoding="utf-8", xml_declaration=True)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def install_mpc_profile(map_text: str, executable: Path, *, appdata: Path | None = None,
                        programdata: Path | None = None, running: bool | None = None) -> tuple[Path, bool]:
    base = appdata or Path(os.environ["APPDATA"])
    shared = programdata or (base / "ProgramData" if appdata is not None else Path(os.environ["PROGRAMDATA"]))
    app = "MPC 3" if executable.name.casefold() == "mpc 3.exe" else "MPC"
    marker = "<!-- ProjectEdmond managed controller profile -->"
    text = map_text.replace("?>", "?>\n" + marker, 1)
    # Akai's desktop manual specifies ProgramData, not AppData, for Windows maps.
    profile = shared / "Akai" / app / "Midi Learn/Project Edmond.xmm"
    managed_write(profile, text, marker)
    # MPC's older map library is shared across Beats/MPC versions.
    if app != "MPC":
        managed_write(shared / "Akai/MPC/Midi Learn/Project Edmond.xmm", text, marker)
    active = process_running(executable) if running is None else running
    applied = False
    if not active:
        applied = configure_mpc_preferences(base / "Akai" / app / (app + ".settings"), profile)
    return profile, applied


def launch_host(executable: Path) -> None:
    if not executable.is_file() or executable.suffix.casefold() != ".exe":
        raise OSError("The selected DAW executable does not exist")
    if not process_running(executable):
        subprocess.Popen([str(executable)], cwd=executable.parent)
