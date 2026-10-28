"""Resources/metadata work without Qt, PyInstaller, Explorer, or a controller."""

import os
import struct
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vega.app import identity
from vega.app.smoke import SmokeSettingsStore
from vega.settings import Settings


class IdentityTests(unittest.TestCase):
    def test_metadata_matches_project(self):
        project = Path(__file__).resolve().parents[1] / "pyproject.toml"
        data = tomllib.loads(project.read_text(encoding="utf-8"))
        self.assertEqual(identity.APP_VERSION, data["project"]["version"])
        self.assertEqual(identity.APP_NAME, "Vega")
        self.assertEqual(identity.EXECUTABLE_NAME, "Vega.exe")
        self.assertEqual(identity.APP_DESCRIPTION, "Vega Guitar Controller")

    def test_icon_contains_all_real_resolutions(self):
        icon = identity.icon_path().read_bytes()
        self.assertEqual(struct.unpack_from("<HHH", icon), (0, 1, 7))
        sizes = []
        for index in range(7):
            width, height, _, _, planes, bits, length, offset = struct.unpack_from("<BBBBHHII", icon, 6 + 16 * index)
            size = width or 256
            self.assertEqual(size, height or 256)
            self.assertEqual((planes, bits), (1, 32))
            png = icon[offset:offset + length]
            self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack_from(">II", png, 16), (size, size))
            sizes.append(size)
        self.assertEqual(sizes, [16, 24, 32, 48, 64, 128, 256])

    def test_icon_path_independent_of_working_directory(self):
        expected = identity.icon_path()
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                self.assertEqual(identity.icon_path(), expected)
                self.assertTrue(expected.is_file())
            finally:
                os.chdir(previous)
            # PyInstaller puts __file__ and data in the same package structure.
            frozen_file = Path(directory) / "_internal" / "vega" / "app" / "identity.py"
            with patch.object(identity, "__file__", str(frozen_file)):
                # Windows CI may spell TEMP with an 8.3 username alias.
                self.assertEqual(identity.icon_path(), frozen_file.resolve().parent / "resources" / "vega.ico")

    def test_packaging_smoke_does_not_save_personal_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text('{"settle_ms": 12}', encoding="utf-8")
            store = SmokeSettingsStore(path)
            self.assertEqual(store.load(), Settings())
            store.save(Settings(4, 0.9))
            self.assertEqual(path.read_text(), '{"settle_ms": 12}')
