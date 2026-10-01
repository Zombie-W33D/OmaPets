"""CLI tests run the same executable and JSON boundary the QML service uses."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "omapets_cli.py"
DEFAULTS = Path(__file__).resolve().parents[1] / "phrases"


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / ".hermes"
        self.root.mkdir()

    def invoke(self, *args):
        return subprocess.run([sys.executable, "-I", str(SCRIPT), "--root", str(self.root),
                               "--defaults", str(DEFAULTS), *args], capture_output=True,
                              text=True, timeout=3)

    def test_surface_cli_returns_only_sanitized_geometry(self):
        import io
        from contextlib import redirect_stdout
        from unittest.mock import patch
        from scripts.omapets_cli import run
        output = io.StringIO()
        with patch("scripts.omapets_surfaces.live_surfaces", return_value={"DP-1": [{"x": 4, "y": 43, "width": 500}]}):
            with redirect_stdout(output):
                self.assertEqual(run(["surfaces"]), 0)
        self.assertEqual(json.loads(output.getvalue()), {"DP-1": [{"x": 4, "y": 43, "width": 500}]})

    def test_snapshot_reports_disabled_default_profile(self):
        result = self.invoke("snapshot")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["profiles"][0]["enabled"], False)

    def test_settings_change_only_known_local_profile(self):
        target = self.root / "profiles" / "aria"
        target.mkdir(parents=True)
        (target / "config.yaml").write_text("name: aria\n")
        self.assertEqual(self.invoke("set", "aria", "mode", "wander").returncode, 0)
        self.assertEqual(json.loads(self.invoke("snapshot").stdout)["profiles"][1]["mode"], "wander")
        self.assertNotEqual(self.invoke("set", "not-real", "enabled", "true").returncode, 0)
        self.assertFalse((self.root / "profiles" / "not-real" / "omapets").exists())

    def test_speed_setting_round_trips_through_cli_and_snapshot(self):
        target = self.root / "profiles" / "aria"
        target.mkdir(parents=True)
        (target / "config.yaml").write_text("name: aria\n")
        self.assertEqual(self.invoke("set", "aria", "speed", "brisk").returncode, 0)
        self.assertEqual(json.loads(self.invoke("snapshot").stdout)["profiles"][1]["speed"], "brisk")
        self.assertNotEqual(self.invoke("set", "aria", "speed", "turbo").returncode, 0)
        self.assertEqual(json.loads(self.invoke("snapshot").stdout)["profiles"][1]["speed"], "brisk")

    def test_enable_without_character_refuses_to_create_config(self):
        result = self.invoke("set", "default", "enabled", "true")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "omapets").exists())

    def test_malformed_field_is_rejected_without_mutation(self):
        result = self.invoke("set", "default", "petId", "../../secret")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "omapets").exists())


if __name__ == "__main__":
    unittest.main()
