"""Packaged native-route startup check without GUI, notes or DAW preference edits."""

import json
from pathlib import Path
import sys

from vega.midi.native_route import ensure_route, native_available
from vega.midi.output import MidoBackend


def write_native_report(path: Path, spec) -> int:
    result = {"app": spec.app, "frozen": bool(getattr(sys, "frozen", False)),
              "native_available": native_available(), "send_port": spec.send_name,
              "host_input": spec.host_name, "connected": False}
    backend = MidoBackend()
    try:
        ensure_route(spec)
        ports = backend.ports()
        if spec.send_name not in ports or spec.host_name not in ports:
            raise OSError("Windows has not exposed both native MIDI ports")
        backend.open(spec.send_name)
        result["connected"] = True
    except Exception as exc:
        result["error"] = str(exc)
    finally:
        try:
            backend.close()
        except Exception as exc:
            result["error"] = str(exc)
            result["connected"] = False
    try:
        with path.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2)
    except OSError:
        return 1
    return 0 if result["connected"] else 1
