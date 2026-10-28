"""Route ownership, DAW preference preservation and connection-button behavior."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import json
import xml.etree.ElementTree as ET

from vega.midi.native_route import RouteSpec, EDMOND_ROUTE, route_payload, endpoint_ids, ensure_route
from vega.midi.host_setup import configure_mpc_preferences, install_fl_profile, install_mpc_profile
from vega.midi.host_setup import FL_SCRIPT


class NativeRouteTests(unittest.TestCase):
    def test_existing_system_pair_survives_missing_local_metadata(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.dict("os.environ", {"LOCALAPPDATA": directory}), \
                patch("vega.midi.native_route.present_endpoint_ids",
                      return_value=set(endpoint_ids(EDMOND_ROUTE).values())), \
                patch("vega.midi.native_route.update_configuration") as update:
            self.assertTrue(ensure_route(EDMOND_ROUTE)["reused"])
            update.assert_not_called()
            self.assertFalse(EDMOND_ROUTE.metadata_path.exists())

    def test_pair_has_distinct_directions_stable_identity_and_midi1_ports(self):
        spec = RouteSpec("ProjectEdmond", "Edmond Drums")
        body = route_payload(spec)["endpointTransportPluginSettings"]
        route = next(iter(next(iter(body.values()))["create"].values()))
        self.assertEqual(route["endpointA"]["name"], "Edmond Drums Send")
        self.assertEqual(route["endpointB"]["name"], "Edmond Drums")
        self.assertFalse(route["endpointA"]["umpOnly"])
        self.assertFalse(route["endpointB"]["umpOnly"])
        self.assertEqual(spec.association, RouteSpec(spec.app, spec.host_name).association)
        self.assertNotEqual(spec.association, RouteSpec("ProjectVega", "Vega Guitar").association)

    def test_unverified_endpoints_are_rejected_without_ownership_file(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict("os.environ", {"LOCALAPPDATA": directory}), \
                    patch("vega.midi.native_route.present_endpoint_ids", return_value=set()), \
                    patch("vega.midi.native_route.output_signature", return_value=()), \
                    patch("vega.midi.native_route.update_configuration", return_value={"success": True,
                                                                                     "endpointA": "foreign"}):
                with self.assertRaisesRegex(OSError, "unexpected"):
                    ensure_route(EDMOND_ROUTE)
                self.assertFalse(EDMOND_ROUTE.metadata_path.exists())

    def test_owned_pair_reuses_without_duplicate_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict("os.environ", {"LOCALAPPDATA": directory}), \
                    patch("vega.midi.native_route.present_endpoint_ids", return_value=set()), \
                    patch("vega.midi.native_route.output_signature", return_value=()) as inventory, \
                    patch("vega.midi.native_route.update_configuration",
                          return_value={"success": True} | endpoint_ids(EDMOND_ROUTE)) as update:
                ensure_route(EDMOND_ROUTE)
                inventory.return_value = ((0, 0, EDMOND_ROUTE.send_name, 0), (0, 0, EDMOND_ROUTE.host_name, 0))
                self.assertTrue(ensure_route(EDMOND_ROUTE)["reused"])
                self.assertEqual(update.call_count, 1)


class HostSetupTests(unittest.TestCase):
    def test_fl_script_reports_attachment_and_notes_without_consuming_midi(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {"LOCALAPPDATA": directory}):
            namespace = {}
            exec(FL_SCRIPT, namespace)
            namespace["OnInit"]()
            path = Path(directory) / "ProjectVega/fl-connection.json"
            self.assertTrue(json.loads(path.read_text())["online"])
            event = SimpleNamespace(status=0x90, data1=40, data2=100, handled=True)
            namespace["OnMidiMsg"](event)
            self.assertFalse(event.handled)
            namespace["_last_report"] = 0
            namespace["OnIdle"]()
            self.assertEqual(json.loads(path.read_text())["note_on_count"], 1)
            namespace["OnDeInit"]()
            self.assertFalse(json.loads(path.read_text())["online"])

    def test_first_mpc_launch_gets_our_preferences_without_a_fake_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "MPC 3/MPC 3.settings"
            self.assertTrue(configure_mpc_preferences(path, Path(directory) / "Project Edmond.xmm"))
            self.assertEqual(ET.parse(path).getroot().tag, "PROPERTIES")
            self.assertFalse(path.with_name(path.name + ".before-project-edmond").exists())

    def test_fl_profile_auto_detection_and_foreign_file_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = install_fl_profile(Path(directory))
            self.assertIn("# supportedDevices=Vega Guitar", path.read_text())
            self.assertIn("event.handled = False", path.read_text())
            self.assertEqual(install_fl_profile(Path(directory)), path)
            path.write_text("user-owned script")
            with self.assertRaisesRegex(OSError, "Preserving"):
                install_fl_profile(Path(directory))
            self.assertEqual(path.read_text(), "user-owned script")

    def test_mpc_enables_only_host_side_and_preserves_other_devices_and_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "MPC 3.settings"
            root = ET.Element("PROPERTIES")
            old_device = {"type": 0, "deviceName": "Existing", "deviceId": "unrelated", "global": False}
            ET.SubElement(root, "VALUE", name="MidiDevices.Table", val=json.dumps({"value0": [old_device]}))
            ET.SubElement(root, "VALUE", name="Unrelated", val="retain")
            ET.ElementTree(root).write(path)
            original = path.read_bytes()
            configure_mpc_preferences(path, Path(directory) / "Project Edmond.xmm")
            parsed = {v.get("name"): v.get("val") for v in ET.parse(path).getroot().findall("VALUE")}
            devices = json.loads(parsed["MidiDevices.Table"])["value0"]
            self.assertEqual(devices[0], old_device)
            self.assertEqual(parsed["Unrelated"], "retain")
            host = next(v for v in devices if v["deviceName"] == "Edmond Drums")
            sender = next(v for v in devices if v["deviceName"] == "Edmond Drums Send")
            self.assertTrue(host["track"] and host["global"] and host["control"])
            self.assertFalse(sender["track"] or sender["global"] or sender["control"])
            self.assertEqual(path.with_name(path.name + ".before-project-edmond").read_bytes(), original)
            configure_mpc_preferences(path, Path(directory) / "Project Edmond.xmm")
            parsed = {v.get("name"): v.get("val") for v in ET.parse(path).getroot().findall("VALUE")}
            self.assertEqual(len(json.loads(parsed["MidiDevices.Table"])["value0"]), 3)

    def test_running_mpc_preferences_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            preferences = base / "Akai/MPC 3/MPC 3.settings"
            preferences.parent.mkdir(parents=True)
            preferences.write_text("preserve while MPC is running")
            profile, applied = install_mpc_profile('<?xml version="1.0"?><MidiLearnMap_/>',
                                                  Path("MPC 3.exe"), appdata=base, running=True)
            self.assertFalse(applied)
            self.assertTrue(profile.is_file())
            self.assertEqual(preferences.read_text(), "preserve while MPC is running")

    def test_malformed_mpc_table_leaves_original_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "MPC.settings"
            path.write_text('<PROPERTIES><VALUE name="MidiDevices.Table" val="{}"/></PROPERTIES>')
            original = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "unsupported"):
                configure_mpc_preferences(path, Path(directory) / "Project Edmond.xmm")
            self.assertEqual(path.read_bytes(), original)
