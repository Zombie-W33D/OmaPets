from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.omapets_data import parse_phrases


class PhraseParsingTests(unittest.TestCase):
    def test_ignores_directions_comments_and_blank_lines(self):
        text = """# Add one short phrase per line.
# Lines beginning with # are instructions, not phrases.

  Thinking of a plan...
# I am checking this carefully.
Ready when you are.
"""
        self.assertEqual(
            parse_phrases(text),
            ["Thinking of a plan...", "Ready when you are."],
        )

    def test_ignores_comment_blocks_in_markdown_phrase_files(self):
        text = """<!--
OmaPets phrase file for thinking.
Put one plain-text phrase on each line below this comment.
-->
Hang on, I'm thinking it through.
<!-- This inline comment line is not a phrase. -->
One more moment.
"""
        self.assertEqual(
            parse_phrases(text),
            ["Hang on, I'm thinking it through.", "One more moment."],
        )


class ProfileDiscoveryTests(unittest.TestCase):
    def test_discovers_default_and_named_profiles_but_skips_symlinked_and_unmarked_dirs(self):
        import tempfile
        from scripts.omapets_data import discover_profile_homes

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / ".hermes"
            profiles = root / "profiles"
            (profiles / "aria").mkdir(parents=True)
            (profiles / "aria" / "config.yaml").write_text("profile: aria\n")
            (profiles / "not-a-profile").mkdir()
            (profiles / ".deleted").mkdir()
            (profiles / ".deleted" / "config.yaml").write_text("marker\n")
            target = Path(temporary) / "linked-target"
            target.mkdir()
            (target / "config.yaml").write_text("profile: target\n")
            (profiles / "linked").symlink_to(target, target_is_directory=True)

            self.assertEqual(
                discover_profile_homes(root),
                [("default", root), ("aria", profiles / "aria")],
            )


class AgentConfigTests(unittest.TestCase):
    def test_missing_config_defaults_to_disabled(self):
        from scripts.omapets_data import default_config

        self.assertFalse(default_config()["enabled"])

    def test_speed_presets_are_bounded_and_older_configs_default_to_slow(self):
        from scripts.omapets_data import default_config, validate_config
        self.assertEqual(default_config()["speed"], "slow")
        self.assertEqual(validate_config({"schemaVersion": 1})["speed"], "slow")
        self.assertEqual(validate_config({"speed": "brisk"})["speed"], "brisk")
        with self.assertRaises(ValueError):
            validate_config({"speed": "instant"})

    def test_phrase_links_must_be_safe_relative_markdown_paths(self):
        from scripts.omapets_data import default_config, validate_config

        config = default_config()
        config["phraseFiles"] = {"yes": "../outside.md"}
        with self.assertRaises(ValueError):
            validate_config(config)

        config["phraseFiles"] = {"yes": "phrases/yes.md"}
        self.assertEqual(validate_config(config)["phraseFiles"], config["phraseFiles"])


class ProfileConfigFileTests(unittest.TestCase):
    def test_missing_profile_config_uses_safe_disabled_defaults(self):
        import tempfile
        from scripts.omapets_data import load_profile_config

        with tempfile.TemporaryDirectory() as temporary:
            config, error = load_profile_config(Path(temporary))
            self.assertFalse(config["enabled"])
            self.assertEqual(error, "")

    def test_malformed_or_symlinked_config_fails_closed(self):
        import tempfile
        from scripts.omapets_data import load_profile_config

        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            data_dir = home / "omapets"
            data_dir.mkdir()
            config_path = data_dir / "config.json"
            config_path.write_text("{broken", encoding="utf-8")
            config, error = load_profile_config(home)
            self.assertFalse(config["enabled"])
            self.assertNotEqual(error, "")

            outside = home / "outside.json"
            outside.write_text('{"enabled": true}', encoding="utf-8")
            config_path.unlink()
            config_path.symlink_to(outside)
            config, error = load_profile_config(home)
            self.assertFalse(config["enabled"])
            self.assertNotEqual(error, "")

    def test_config_write_is_atomic_private_and_round_trips(self):
        import os
        import stat
        import tempfile
        from scripts.omapets_data import default_config, load_profile_config, write_profile_config

        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            config = default_config()
            config.update({"enabled": True, "petId": "socksy", "mode": "wander"})
            write_profile_config(home, config)
            loaded, error = load_profile_config(home)
            self.assertEqual(error, "")
            self.assertEqual(loaded, config)
            self.assertEqual(stat.S_IMODE((home / "omapets").stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((home / "omapets" / "config.json").stat().st_mode), 0o600)
            self.assertEqual(os.listdir(home / "omapets"), ["config.json"])


class OpenPetsMetadataTests(unittest.TestCase):
    def test_unmarked_v1_and_marked_v2_use_the_documented_atlas_rows(self):
        from scripts.omapets_data import validate_pet_metadata

        base = {
            "id": "socksy",
            "displayName": "Socksy",
            "description": "A friendly pet.",
            "spritesheetPath": "spritesheet.webp",
        }
        v1 = validate_pet_metadata(base, "socksy")
        self.assertEqual(v1["spriteVersionNumber"], 1)
        self.assertEqual(v1["rowCount"], 9)

        v2 = validate_pet_metadata({**base, "spriteVersionNumber": 2}, "socksy")
        self.assertEqual(v2["spriteVersionNumber"], 2)
        self.assertEqual(v2["rowCount"], 11)
        self.assertEqual(v2["neutralIdleCell"], {"row": 0, "column": 6})

    def test_webp_header_enforces_v2_canvas_alpha_and_animation_rules(self):
        from scripts.omapets_data import inspect_webp_header, validate_pet_metadata, validate_spritesheet

        def header(width, height, flags=0x10):
            payload = (
                bytes([flags, 0, 0, 0])
                + (width - 1).to_bytes(3, "little")
                + (height - 1).to_bytes(3, "little")
            )
            chunk = b"VP8X" + len(payload).to_bytes(4, "little") + payload
            body = b"WEBP" + chunk
            return b"RIFF" + len(body).to_bytes(4, "little") + body

        v2 = validate_pet_metadata(
            {
                "id": "socksy",
                "displayName": "Socksy",
                "description": "A friendly pet.",
                "spritesheetPath": "spritesheet.webp",
                "spriteVersionNumber": 2,
            },
            "socksy",
        )
        good = header(1536, 2288)
        info = inspect_webp_header(good, len(good))
        self.assertEqual(validate_spritesheet(v2, info, len(good))["frameWidth"], 192)
        for invalid in (header(1536, 2288, flags=0), header(1536, 2288, flags=0x12)):
            with self.assertRaises(ValueError):
                validate_spritesheet(v2, inspect_webp_header(invalid, len(invalid)), len(invalid))

    def test_v1_allows_integer_scale_atlas_but_bounds_decoded_pixels(self):
        from scripts.omapets_data import inspect_webp_header, validate_pet_metadata, validate_spritesheet

        metadata = validate_pet_metadata(
            {
                "id": "socksy",
                "displayName": "Socksy",
                "description": "A friendly pet.",
                "spritesheetPath": "spritesheet.webp",
            },
            "socksy",
        )
        payload = bytes([0x10, 0, 0, 0]) + (3071).to_bytes(3, "little") + (3743).to_bytes(3, "little")
        chunk = b"VP8X" + len(payload).to_bytes(4, "little") + payload
        body = b"WEBP" + chunk
        webp = b"RIFF" + len(body).to_bytes(4, "little") + body
        info = inspect_webp_header(webp, len(webp))
        layout = validate_spritesheet(metadata, info, len(webp))
        self.assertEqual((layout["frameWidth"], layout["frameHeight"]), (384, 416))
        with self.assertRaises(ValueError):
            validate_spritesheet(metadata, {**info, "width": 10000, "height": 10000}, len(webp))

    def test_rejects_unsafe_ids_paths_and_non_v2_version_markers(self):
        from scripts.omapets_data import validate_pet_metadata

        base = {
            "id": "socksy",
            "displayName": "Socksy",
            "description": "A friendly pet.",
            "spritesheetPath": "spritesheet.webp",
        }
        for changed in (
            {"id": "../socksy"},
            {"id": "builtin"},
            {"spritesheetPath": "../outside.webp"},
            {"spriteVersionNumber": 1},
        ):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                validate_pet_metadata({**base, **changed}, changed.get("id", "socksy"))


if __name__ == "__main__":
    unittest.main()
