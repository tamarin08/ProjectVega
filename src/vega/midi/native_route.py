"""App-owned MIDI 1.0 routes through Windows' installed MIDI Service.

Uses the system COM transport contract from Microsoft MIDI's WindowsMidiServices.idl
and LoopbackMidiTransport. No SDK binary, driver, service installer or tray utility
is redistributed. Windows 11 25H2 with Windows MIDI Service is required.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
import getpass
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid

from vega.midi.windows_ports import output_signature

LOOPBACK_TRANSPORT = "{942BF02D-93C0-4EA8-B03E-D51156CA75E1}"
TRANSPORT_CLASS = "2BA15E4E-5417-4A66-85B8-2B2260EFBC84"
TRANSPORT_INTERFACE = "EA264200-3328-49E5-8815-73649A8748BE"
CONFIG_INTERFACE = "f19dd642-1809-4497-9eee-f230b11bd6fb"


@dataclass(frozen=True)
class RouteSpec:
    app: str
    host_name: str

    @property
    def send_name(self) -> str:
        return self.host_name + " Send"

    @property
    def association(self) -> str:
        identity = os.environ.get("USERDOMAIN", "") + "\\" + getpass.getuser()
        return str(uuid.uuid5(uuid.NAMESPACE_URL, "ProjectVega/native-midi/" + self.app + "/" + identity))

    @property
    def unique_prefix(self) -> str:
        return self.app.lower() + "." + self.association.replace("-", "")

    @property
    def metadata_path(self) -> Path:
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / self.app / "native-route.json"


VEGA_ROUTE = RouteSpec("ProjectVega", "Vega Guitar")
EDMOND_ROUTE = RouteSpec("ProjectEdmond", "Edmond Drums")


def route_payload(spec: RouteSpec) -> dict:
    return {"endpointTransportPluginSettings": {LOOPBACK_TRANSPORT: {"create": {
        "{" + spec.association + "}": {
            "endpointA": {"name": spec.send_name, "description": spec.app + " application output",
                          "uniqueIdentifier": spec.unique_prefix + ".send", "umpOnly": False},
            "endpointB": {"name": spec.host_name, "description": spec.app + " DAW input",
                          "uniqueIdentifier": spec.unique_prefix + ".host", "umpOnly": False},
        }
    }}}}


def native_available() -> bool:
    return (sys.platform == "win32" and sys.getwindowsversion().build >= 26200
            and (Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/Midi2.MidiSrvTransport.dll").is_file())


def update_configuration(payload: dict) -> dict:
    """Bound to the system transport's IUnknown/IMidiTransportConfigurationManager."""
    if not native_available():
        raise OSError("Native routing requires updated Windows 11 25H2 or later with Windows MIDI Service.")
    from ctypes import wintypes

    class Guid(ctypes.Structure):
        _fields_ = [("a", wintypes.DWORD), ("b", wintypes.WORD), ("c", wintypes.WORD),
                    ("d", ctypes.c_ubyte * 8)]

        def __init__(self, value):
            super().__init__()
            ctypes.memmove(ctypes.byref(self), uuid.UUID(value).bytes_le, 16)

    ole = ctypes.OleDLL("ole32")
    ole.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    ole.CoInitializeEx.restype = ctypes.c_long
    ole.CoCreateInstance.argtypes = [ctypes.POINTER(Guid), ctypes.c_void_p, wintypes.DWORD,
                                    ctypes.POINTER(Guid), ctypes.POINTER(ctypes.c_void_p)]
    ole.CoCreateInstance.restype = ctypes.c_long
    ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]

    def check(hr):
        if hr < 0:
            raise OSError(f"Windows MIDI Service returned 0x{hr & 0xffffffff:08X}")

    def call(pointer, index, types=(), *args):
        table = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        function = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *types)(table[index])
        result = function(pointer, *args)
        if index != 2:  # IUnknown::Release returns a reference count, not an HRESULT.
            check(result)

    initialized = ole.CoInitializeEx(None, 0)
    if initialized < 0 and initialized != -2147417850:  # RPC_E_CHANGED_MODE: Qt already owns this apartment.
        check(initialized)
    transport, config, response = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p()
    config_initialized = False
    try:
        check(ole.CoCreateInstance(ctypes.byref(Guid(TRANSPORT_CLASS)), None, 1,
                                  ctypes.byref(Guid(TRANSPORT_INTERFACE)), ctypes.byref(transport)))
        call(transport, 3, (ctypes.POINTER(Guid), ctypes.POINTER(ctypes.c_void_p)),
             ctypes.byref(Guid(CONFIG_INTERFACE)), ctypes.byref(config))
        call(config, 3, (Guid, ctypes.c_void_p, ctypes.c_void_p),
             Guid("00000000-0000-0000-0000-000000000000"), None, None)
        config_initialized = True
        call(config, 4, (wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p)),
             json.dumps(payload), ctypes.byref(response))
        if not response:
            raise OSError("Windows MIDI Service returned no route result")
        result = json.loads(ctypes.wstring_at(response))
        if not isinstance(result, dict):
            raise OSError("Windows MIDI Service returned an invalid result")
        return result
    finally:
        if response:
            ole.CoTaskMemFree(response)
        if config:
            try:
                if config_initialized:
                    call(config, 5)
            finally:
                call(config, 2)
        if transport:
            call(transport, 2)
        if initialized >= 0:
            ole.CoUninitialize()


def endpoint_ids(spec: RouteSpec) -> dict[str, str]:
    suffix = "#{e7cce071-3c03-423f-88d3-f1045d02552b}"
    return {"endpointA": "\\\\?\\swd#midisrv#midiu_loop_a_" + spec.unique_prefix + ".send" + suffix,
            "endpointB": "\\\\?\\swd#midisrv#midiu_loop_b_" + spec.unique_prefix + ".host" + suffix}


def present_endpoint_ids() -> set[str]:
    """Read active system interfaces; friendly MIDI names alone do not prove ownership.

    https://learn.microsoft.com/windows/win32/api/cfgmgr32/nf-cfgmgr32-cm_get_device_interface_listw
    """
    if sys.platform != "win32":
        return set()
    from ctypes import wintypes
    api = ctypes.WinDLL("cfgmgr32")
    interface = (ctypes.c_ubyte * 16).from_buffer_copy(
        uuid.UUID("e7cce071-3c03-423f-88d3-f1045d02552b").bytes_le)
    api.CM_Get_Device_Interface_List_SizeW.argtypes = [ctypes.POINTER(wintypes.ULONG),
                                                       ctypes.c_void_p, wintypes.LPCWSTR, wintypes.ULONG]
    api.CM_Get_Device_Interface_List_SizeW.restype = wintypes.ULONG
    api.CM_Get_Device_Interface_ListW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR,
                                                wintypes.LPWSTR, wintypes.ULONG, wintypes.ULONG]
    api.CM_Get_Device_Interface_ListW.restype = wintypes.ULONG
    for _ in range(3):
        length = wintypes.ULONG()
        code = api.CM_Get_Device_Interface_List_SizeW(ctypes.byref(length), interface, None, 0)
        if code:
            raise OSError(f"Windows MIDI interface inventory failed: {code}")
        buffer = ctypes.create_unicode_buffer(max(2, length.value))
        code = api.CM_Get_Device_Interface_ListW(interface, None, buffer, len(buffer), 0)
        if code == 0x1A:  # CR_BUFFER_SMALL: a device arrived during enumeration.
            continue
        if code:
            raise OSError(f"Windows MIDI interface inventory failed: {code}")
        return {value.lower() for value in buffer[:].split("\0") if value}
    raise OSError("Windows MIDI interfaces changed repeatedly; retry connection")


def ensure_route(spec: RouteSpec) -> dict:
    """Create a deterministic per-user route, or reuse only a verified app-owned pair."""
    expected = endpoint_ids(spec)
    # Python Store and a frozen EXE can have different local-data virtualization.
    # Reuse the exact per-user system identities even if metadata was lost or moved.
    present = present_endpoint_ids()
    if all(value.lower() in present for value in expected.values()):
        return expected | {"success": True, "reused": True}
    names = {entry[2] for entry in (output_signature() or ())}
    # The service persists endpoints until its next restart. Creation with the
    # same association is idempotent from our side; never delete other routes.
    owned = False
    try:
        saved = json.loads(spec.metadata_path.read_text(encoding="utf-8"))
        owned = (saved.get("association") == spec.association
                 and all(saved.get(key, "").lower() == value.lower() for key, value in expected.items()))
    except (OSError, ValueError, AttributeError):
        pass
    if owned and spec.send_name in names and spec.host_name in names:
        return expected | {"success": True, "reused": True}
    result = update_configuration(route_payload(spec))
    if not result.get("success"):
        raise OSError("Native route could not be created: " + str(result.get("message", result)))
    if any(str(result.get(key, "")).lower() != value.lower() for key, value in expected.items()):
        raise OSError("Windows returned unexpected MIDI endpoint identities")
    spec.metadata_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=spec.metadata_path.parent,
                                         prefix="route-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(result | {"association": spec.association}, stream, indent=2)
        os.replace(temporary, spec.metadata_path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return result
