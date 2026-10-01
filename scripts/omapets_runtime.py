"""Bounded, read-only OpenPets/Hermes snapshot for the hosted OmaPets service."""

import json
import os
from pathlib import Path
import random
import stat

from scripts.omapets_data import (
    CATEGORIES, _open_directory_chain, _read_file_at, discover_profile_homes,
    inspect_webp_header, load_profile_config, parse_phrases,
    validate_pet_metadata, validate_spritesheet,
)

MAX_PROFILES = 12
MAX_PETS = 32
MAX_PHRASE_BYTES = 4096
MAX_PHRASES = 8
MAX_PHRASE_CHARS = 100
MAX_SNAPSHOT_BYTES = 48 * 1024

# The nine universal V1 rows are retained at the same indices in V2.
# OpenPets' reaction-animation-mapping.ts supplies the rows and frame counts.
ANIMATION_ROWS = {
    "idle": (0, 6), "running-right": (1, 8), "running-left": (2, 8),
    "waving": (3, 4), "jumping": (4, 5), "failed": (5, 8),
    "waiting": (6, 6), "running": (7, 6), "review": (8, 6),
}
DEFAULT_ANIMATIONS = {
    "thinking": "review", "waiting_on_you": "waiting",
    "waiting_on_task": "waiting", "yes": "waving", "no": "failed",
    "success": "jumping", "finished": "idle", "failed": "failed",
}


def resolve_animation(category, overrides):
    """Return the supported atlas row and frame count, or idle."""
    if category not in CATEGORIES or not isinstance(overrides, dict):
        return ANIMATION_ROWS["idle"]
    name = overrides.get(category, DEFAULT_ANIMATIONS[category])
    return ANIMATION_ROWS.get(name, ANIMATION_ROWS["idle"])


def select_phrase(phrases, previous="", pick=random.choice):
    """Select a line at random without immediately repeating it when possible."""
    available = [text for text in phrases if text != previous] if len(phrases) > 1 else phrases
    return pick(available) if available else ""


def _read_phrase(home, relative):
    fd = None
    try:
        fd = _open_directory_chain(home)
        data = _read_file_at(fd, tuple(relative.split("/")), MAX_PHRASE_BYTES)
        phrases = parse_phrases(data.decode("utf-8"))
        return [line for line in phrases if len(line) <= MAX_PHRASE_CHARS
                and all(ord(char) >= 32 for char in line)][:MAX_PHRASES]
    except (OSError, UnicodeError, ValueError):
        return []
    finally:
        if fd is not None:
            os.close(fd)


def _read_pet(pets_home, pet_id):
    """Resolve a local package with no symlink traversal; never execute pet content."""
    package = pets_home / pet_id
    fd = None
    image_fd = None
    try:
        fd = _open_directory_chain(package)
        raw = _read_file_at(fd, ("pet.json",), 8192)
        metadata = validate_pet_metadata(json.loads(raw.decode("utf-8")), pet_id)
        image_fd = os.open("spritesheet.webp", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
        info = os.fstat(image_fd)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("not a regular sprite file")
        image = validate_spritesheet(
            metadata, inspect_webp_header(os.read(image_fd, 65536), info.st_size), info.st_size
        )
        return {
            "source": (package / "spritesheet.webp").as_uri(),
            "name": metadata["displayName"], "version": metadata["version"],
            "frameWidth": image["frameWidth"], "frameHeight": image["frameHeight"],
            "columns": image["columns"], "rows": image["rows"],
        }
    except (OSError, UnicodeError, ValueError, TypeError, RecursionError, json.JSONDecodeError):
        return None
    finally:
        if image_fd is not None:
            os.close(image_fd)
        if fd is not None:
            os.close(fd)


def _pet_ids(pets_home):
    try:
        candidates = sorted(pets_home.iterdir(), key=lambda child: child.name)
    except OSError:
        return []
    result = []
    for child in candidates[:128]:
        if _read_pet(pets_home, child.name):
            result.append(child.name)
            if len(result) >= MAX_PETS:
                break
    return result


def build_snapshot(hermes_root, defaults_home):
    """Provide bounded local profile settings, assets and phrases to QML."""
    root = Path(hermes_root).expanduser()
    defaults = Path(defaults_home)
    pets_home = root / "pets"
    pet_ids = _pet_ids(pets_home)
    profiles = []
    for profile_id, home in discover_profile_homes(root)[:MAX_PROFILES]:
        config, error = load_profile_config(home)
        item = {
            "id": profile_id, "enabled": config["enabled"],
            "petId": config["petId"], "mode": config["mode"],
            "screen": config["screen"], "position": config["position"],
            "scale": config["scale"], "pet": None, "error": error,
        }
        if config["enabled"]:
            pet = _read_pet(pets_home, config["petId"]) if config["petId"] else None
            if pet is None:
                item["error"] = "Select an installed, valid OpenPets character"
            else:
                item["pet"] = pet
                item["animations"] = {
                    category: {"row": resolve_animation(category, config["animations"])[0],
                               "frames": resolve_animation(category, config["animations"])[1]}
                    for category in CATEGORIES
                }
                item["phrases"] = {
                    category: _read_phrase(home / "omapets", config["phraseFiles"][category])
                    if category in config["phraseFiles"]
                    else _read_phrase(defaults, category + ".md")
                    for category in CATEGORIES
                }
        profiles.append(item)
    snapshot = {"schemaVersion": 1, "petIds": pet_ids, "profiles": profiles}
    if len(json.dumps(snapshot, ensure_ascii=False).encode("utf-8")) > MAX_SNAPSHOT_BYTES:
        raise ValueError("snapshot exceeds size limit")
    return snapshot
