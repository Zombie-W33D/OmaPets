"""Behavioral tests for the OmaPets read-only snapshot and event model."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.omapets_runtime import build_snapshot, select_phrase, resolve_animation
from scripts.omapets_data import default_config, write_profile_config


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / ".hermes"
        self.root.mkdir()
        self.defaults = Path(__file__).resolve().parents[1] / "phrases"

    def add_pet(self):
        package = self.root / "pets" / "socksy"
        package.mkdir(parents=True)
        (package / "pet.json").write_text(json.dumps({
            "id": "socksy", "displayName": "Socksy", "description": "A sock elf",
            "spriteVersionNumber": 2, "spritesheetPath": "spritesheet.webp",
        }))
        payload = bytes([0x10, 0, 0, 0]) + (1535).to_bytes(3, "little") + (2287).to_bytes(3, "little")
        chunk = b"VP8X" + len(payload).to_bytes(4, "little") + payload
        body = b"WEBP" + chunk
        (package / "spritesheet.webp").write_bytes(b"RIFF" + len(body).to_bytes(4, "little") + body)
        return package

    def test_surface_snapshot_uses_only_visible_windows_and_bar_on_correct_monitor(self):
        from scripts.omapets_surfaces import surfaces_by_monitor
        monitors = [
            {"id": 0, "name": "DP-1", "x": 3072, "y": 0, "width": 3840, "height": 2160,
             "scale": 1.25, "activeWorkspace": {"id": 1}, "specialWorkspace": {"id": 0}},
            {"id": 1, "name": "DP-2", "x": 0, "y": 0, "width": 1920, "height": 1080,
             "scale": 0.625, "activeWorkspace": {"id": 6}, "specialWorkspace": {"id": 0}},
        ]
        clients = [
            {"monitor": 0, "at": [3084, 83], "size": [1532, 1268], "workspace": {"id": 1}, "mapped": True, "hidden": False},
            {"monitor": 0, "at": [3084, 55], "size": [1532, 1268], "workspace": {"id": -98}, "mapped": True, "hidden": False},
            {"monitor": 1, "at": [12, 55], "size": [1517, 1661], "workspace": {"id": 6}, "mapped": True, "hidden": False},
            {"monitor": 0, "at": [3084, 83], "size": [1532, 1268], "workspace": {"id": 1}, "mapped": False, "hidden": False},
        ]
        layers = {"DP-1": {"levels": {"2": [{"namespace": "omarchy-bar", "x": 3072, "y": 0, "w": 3072, "h": 43},
                                              {"namespace": "omapets", "x": 3072, "y": 0, "w": 3072, "h": 1728}]}},
                  "DP-2": {"levels": {"2": [{"namespace": "omarchy-bar", "x": 0, "y": 0, "w": 3072, "h": 43}]}}}
        result = surfaces_by_monitor(monitors, clients, layers)
        self.assertEqual(result["DP-1"], [{"x": 12, "y": 83, "width": 1532}, {"x": 0, "y": 43, "width": 3072}])
        self.assertEqual(result["DP-2"], [{"x": 12, "y": 55, "width": 1517}, {"x": 0, "y": 43, "width": 3072}])

    def test_all_activity_states_have_distinct_nonempty_shared_defaults(self):
        self.add_pet()
        config = default_config()
        config.update(enabled=True, petId="socksy")
        write_profile_config(self.root, config)
        snapshot = build_snapshot(self.root, self.defaults)["profiles"][0]
        for state in ("thinking", "working", "waiting_on_you", "waiting_on_task", "finished", "failed"):
            with self.subTest(state=state):
                self.assertGreaterEqual(len(snapshot["phrases"][state]), 3)
                self.assertGreaterEqual(snapshot["animations"][state]["frames"], 1)

    def test_working_default_has_plausible_phrases_and_bottom_row_animation(self):
        self.add_pet()
        config = default_config()
        config.update(enabled=True, petId="socksy")
        write_profile_config(self.root, config)
        snapshot = build_snapshot(self.root, self.defaults)["profiles"][0]
        self.assertGreaterEqual(len(snapshot["phrases"]["working"]), 3)
        self.assertTrue(all(isinstance(line, str) and line for line in snapshot["phrases"]["working"]))
        self.assertEqual(snapshot["animations"]["working"], {"row": 8, "frames": 6})

    def test_missing_config_lists_disabled_profile_without_render_asset(self):
        self.add_pet()
        snapshot = build_snapshot(self.root, self.defaults)
        self.assertEqual(snapshot["petIds"], ["socksy"])
        self.assertEqual(snapshot["profiles"], [{"id": "default", "enabled": False,
                                               "petId": "", "mode": "stay", "speed": "slow", "screen": "",
                                               "position": {"x": 0.85, "y": 0.9}, "scale": 3,
                                               "pet": None, "error": ""}])

    def test_enabled_profile_resolves_local_atlas_and_linked_phrases(self):
        package = self.add_pet()
        profile = self.root / "profiles" / "aria"
        profile.mkdir(parents=True)
        (profile / "config.yaml").write_text("name: aria\n")
        config = default_config()
        config.update(enabled=True, petId="socksy", phraseFiles={"yes": "custom/yes.md",
                                                                  "no": "custom/no.md"})
        write_profile_config(profile, config)
        custom = profile / "omapets" / "custom"
        custom.mkdir()
        (custom / "yes.md").write_text("# Directions\nYep, that's right.\n")
        (custom / "no.md").write_text("# Silence by choice\n")
        snapshot = build_snapshot(self.root, self.defaults)
        result = snapshot["profiles"][1]
        self.assertEqual(result["id"], "aria")
        self.assertEqual(result["pet"]["source"], (package / "spritesheet.webp").as_uri())
        self.assertEqual(result["pet"]["frameWidth"], 192)
        self.assertEqual(result["pet"]["version"], 2)
        self.assertEqual(result["phrases"]["yes"], ["Yep, that's right."])
        self.assertEqual(result["phrases"]["no"], [])
        self.assertTrue(snapshot["profiles"][0]["enabled"] is False)

    def test_symlinked_custom_phrase_is_silent_not_default(self):
        self.add_pet()
        config = default_config()
        config.update(enabled=True, petId="socksy", phraseFiles={"yes": "linked.md"})
        write_profile_config(self.root, config)
        (self.root / "omapets" / "linked.md").symlink_to(self.defaults / "yes.md")
        snapshot = build_snapshot(self.root, self.defaults)
        self.assertEqual(snapshot["profiles"][0]["phrases"]["yes"], [])

    def test_missing_or_invalid_package_cannot_be_rendered(self):
        self.add_pet()
        config = default_config()
        config.update(enabled=True, petId="socksy")
        write_profile_config(self.root, config)
        (self.root / "pets" / "socksy" / "spritesheet.webp").unlink()
        result = build_snapshot(self.root, self.defaults)["profiles"][0]
        self.assertIsNone(result["pet"])
        self.assertNotEqual(result["error"], "")

    def test_animation_mapping_uses_idle_on_unsupported_override(self):
        self.assertEqual(resolve_animation("thinking", {}), (8, 6))
        self.assertEqual(resolve_animation("success", {}), (4, 5))
        self.assertEqual(resolve_animation("finished", {}), (0, 6))
        self.assertEqual(resolve_animation("yes", {"yes": "unsupported"}), (0, 6))

    def test_phrase_selection_avoids_immediate_repeat(self):
        self.assertEqual(select_phrase(["one", "two"], "one", pick=lambda items: items[0]), "two")
        self.assertEqual(select_phrase([], "one"), "")
        self.assertEqual(select_phrase(["one"], "one"), "one")


if __name__ == "__main__":
    unittest.main()
