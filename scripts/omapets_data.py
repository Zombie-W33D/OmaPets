"""Pure data helpers for OmaPets' local profile and phrase model."""


def parse_phrases(text):
    """Return non-empty, non-comment lines as plain-text phrases."""
    if not isinstance(text, str):
        return []
    phrases = []
    in_html_comment = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        segments = []
        cursor = 0
        while cursor < len(line):
            if in_html_comment:
                closing = line.find("-->", cursor)
                if closing < 0:
                    cursor = len(line)
                    break
                in_html_comment = False
                cursor = closing + 3
                continue
            opening = line.find("<!--", cursor)
            if opening < 0:
                segments.append(line[cursor:])
                break
            segments.append(line[cursor:opening])
            closing = line.find("-->", opening + 4)
            if closing < 0:
                in_html_comment = True
                cursor = len(line)
                break
            cursor = closing + 3
        phrase = "".join(segments).strip()
        if phrase and not phrase.startswith("#"):
            phrases.append(phrase)
    return phrases


def discover_profile_homes(hermes_root, active_home=None):
    """Return the default Hermes home and marked immediate named profiles."""
    from pathlib import Path
    import re
    import stat

    root = Path(hermes_root).expanduser()
    try:
        root_mode = root.lstat().st_mode
    except OSError:
        return []
    if stat.S_ISLNK(root_mode) or not stat.S_ISDIR(root_mode):
        return []

    result = [("default", root)]
    profile_root = root / "profiles"
    try:
        profile_mode = profile_root.lstat().st_mode
    except OSError:
        profile_mode = None
    if profile_mode is not None and stat.S_ISDIR(profile_mode):
        for child in sorted(profile_root.iterdir(), key=lambda item: item.name.casefold()):
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", child.name) or ".." in child.name:
                continue
            try:
                child_mode = child.lstat().st_mode
                config_mode = (child / "config.yaml").lstat().st_mode
            except OSError:
                continue
            if stat.S_ISDIR(child_mode) and stat.S_ISREG(config_mode):
                result.append((child.name, child))

    if active_home is not None:
        active = Path(active_home).expanduser()
        try:
            active_mode = active.lstat().st_mode
        except OSError:
            active_mode = None
        if active_mode is not None and stat.S_ISDIR(active_mode) and not stat.S_ISLNK(active_mode):
            if all(active != home for _, home in result):
                name = active.name or "custom"
                if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", name) and ".." not in name:
                    result.append((name, active))
    return result


CATEGORIES = (
    "thinking",
    "working",
    "waiting_on_you",
    "waiting_on_task",
    "yes",
    "no",
    "success",
    "finished",
    "failed",
)


def default_config():
    """Return an independent, disabled-by-default per-profile config."""
    return {
        "schemaVersion": 1,
        "enabled": False,
        "petId": "",
        "mode": "stay",
        "speed": "slow",
        "screen": "",
        "position": {"x": 0.85, "y": 0.9},
        "scale": 3,
        "animations": {},
        "phraseFiles": {},
    }


def _safe_markdown_path(value):
    from pathlib import PurePosixPath

    if not isinstance(value, str) or not value or len(value) > 256:
        return False
    if "\\" in value or "\x00" in value or "\n" in value or "\r" in value:
        return False
    path = PurePosixPath(value)
    return (
        not path.is_absolute()
        and value == path.as_posix()
        and all(part not in ("", ".", "..") for part in path.parts)
        and path.suffix.lower() == ".md"
    )


def validate_config(config):
    """Validate and normalize the supported per-profile settings."""
    import math
    import re

    if not isinstance(config, dict):
        raise ValueError("config must be an object")
    allowed = set(default_config())
    unknown = set(config) - allowed
    if unknown:
        raise ValueError("unknown config field")
    result = default_config()
    result.update(config)
    if type(result["schemaVersion"]) is not int or result["schemaVersion"] != 1:
        raise ValueError("unsupported config schemaVersion")
    if type(result["enabled"]) is not bool:
        raise ValueError("enabled must be a boolean")
    pet_id = result["petId"]
    if not isinstance(pet_id, str) or len(pet_id) > 64 or (
        pet_id and (not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]*", pet_id) or ".." in pet_id)
    ):
        raise ValueError("petId must be a safe package id or empty")
    if result["mode"] not in ("stay", "wander"):
        raise ValueError("mode must be stay or wander")
    if result["speed"] not in ("slow", "normal", "brisk"):
        raise ValueError("speed must be slow, normal or brisk")
    screen = result["screen"]
    if not isinstance(screen, str) or len(screen) > 64 or any(ord(char) < 32 for char in screen):
        raise ValueError("screen must be a short plain-text name")

    position = result["position"]
    if not isinstance(position, dict) or set(position) != {"x", "y"}:
        raise ValueError("position must contain x and y")
    normalized_position = {}
    for axis in ("x", "y"):
        value = position[axis]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("position coordinates must be numbers")
        value = float(value)
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError("position coordinates must be between 0 and 1")
        normalized_position[axis] = value
    result["position"] = normalized_position

    scale = result["scale"]
    if type(scale) is not int or not 1 <= scale <= 6:
        raise ValueError("scale must be an integer from 1 to 6")

    animations = result["animations"]
    if not isinstance(animations, dict) or set(animations) - set(CATEGORIES):
        raise ValueError("animations must map supported categories")
    for category, animation in animations.items():
        if not isinstance(animation, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,31}", animation):
            raise ValueError("animation names must be simple identifiers")

    phrase_files = result["phraseFiles"]
    if not isinstance(phrase_files, dict) or set(phrase_files) - set(CATEGORIES):
        raise ValueError("phraseFiles must map supported categories")
    if any(not _safe_markdown_path(path) for path in phrase_files.values()):
        raise ValueError("phrase file links must be safe relative .md paths")
    result["animations"] = dict(animations)
    result["phraseFiles"] = dict(phrase_files)
    return result


MAX_CONFIG_BYTES = 32 * 1024


def _open_directory_chain(path):
    """Open an absolute directory without following any symlink component."""
    import os
    from pathlib import Path

    directory = Path(path).expanduser()
    if not directory.is_absolute() or ".." in directory.parts:
        raise ValueError("directory must be an absolute safe path")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(directory.anchor, flags)
    try:
        for component in directory.parts[1:]:
            child = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _read_file_at(root_fd, relative_parts, limit):
    """Read one bounded regular file below an already-open trusted directory."""
    import os
    import stat

    if not relative_parts or any(part in ("", ".", "..") or "/" in part or "\\" in part for part in relative_parts):
        raise ValueError("unsafe relative file path")
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    current_fd = os.dup(root_fd)
    try:
        for component in relative_parts[:-1]:
            next_fd = os.open(component, directory_flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        file_fd = os.open(
            relative_parts[-1],
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=current_fd,
        )
        try:
            metadata = os.fstat(file_fd)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > limit:
                raise ValueError("unsafe or oversized file")
            data = bytearray()
            while len(data) <= limit:
                chunk = os.read(file_fd, min(8192, limit + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
            if len(data) > limit:
                raise ValueError("file exceeds size limit")
            return bytes(data)
        finally:
            os.close(file_fd)
    finally:
        os.close(current_fd)


def load_profile_config(profile_home):
    """Load a profile config safely; return disabled defaults on invalid input."""
    import json
    import os

    def reject_constant(_value):
        raise ValueError("non-finite JSON number")

    def reject_duplicate_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    profile_fd = None
    data_fd = None
    try:
        profile_fd = _open_directory_chain(profile_home)
        data_fd = os.open(
            "omapets",
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=profile_fd,
        )
        raw = _read_file_at(data_fd, ("config.json",), MAX_CONFIG_BYTES)
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_constant,
        )
        return validate_config(value), ""
    except FileNotFoundError:
        return default_config(), ""
    except (OSError, UnicodeError, ValueError, RecursionError, json.JSONDecodeError):
        return default_config(), "OmaPets configuration is invalid or unsafe"
    finally:
        if data_fd is not None:
            os.close(data_fd)
        if profile_fd is not None:
            os.close(profile_fd)


def write_profile_config(profile_home, config):
    """Atomically write a validated config with owner-only permissions."""
    import json
    import os
    import secrets

    normalized = validate_config(config)
    raw = (json.dumps(normalized, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if len(raw) > MAX_CONFIG_BYTES:
        raise ValueError("config exceeds size limit")

    profile_fd = _open_directory_chain(profile_home)
    data_fd = None
    temp_name = None
    try:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            data_fd = os.open("omapets", flags, dir_fd=profile_fd)
        except FileNotFoundError:
            try:
                os.mkdir("omapets", mode=0o700, dir_fd=profile_fd)
            except FileExistsError:
                pass
            data_fd = os.open("omapets", flags, dir_fd=profile_fd)

        for _ in range(4):
            temp_name = ".config.json." + secrets.token_hex(8)
            try:
                output_fd = os.open(
                    temp_name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                    0o600,
                    dir_fd=data_fd,
                )
                break
            except FileExistsError:
                temp_name = None
        else:
            raise OSError("unable to allocate config temp file")

        try:
            view = memoryview(raw)
            while view:
                written = os.write(output_fd, view)
                if written <= 0:
                    raise OSError("short config write")
                view = view[written:]
            os.fsync(output_fd)
        finally:
            os.close(output_fd)

        os.replace(temp_name, "config.json", src_dir_fd=data_fd, dst_dir_fd=data_fd)
        temp_name = None
        os.fsync(data_fd)
        return normalized
    finally:
        if temp_name is not None and data_fd is not None:
            try:
                os.unlink(temp_name, dir_fd=data_fd)
            except FileNotFoundError:
                pass
        if data_fd is not None:
            os.close(data_fd)
        os.close(profile_fd)


def validate_pet_metadata(value, folder_name):
    """Validate OpenPets V1/V2 pet.json identity and atlas metadata."""
    import re

    def safe_id(candidate):
        return (
            isinstance(candidate, str)
            and re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", candidate) is not None
            and candidate != "builtin"
        )

    if not safe_id(folder_name):
        raise ValueError("pet folder name is invalid")
    if not isinstance(value, dict):
        raise ValueError("pet.json must be an object")
    if value.get("id") != folder_name:
        raise ValueError("pet id must match its folder name")
    if not safe_id(value.get("id")):
        raise ValueError("pet id is invalid")

    display_name = value.get("displayName")
    description = value.get("description")
    if not isinstance(display_name, str) or not display_name.strip() or len(display_name) > 80:
        raise ValueError("pet displayName is invalid")
    if not isinstance(description, str) or not description.strip() or len(description) > 500:
        raise ValueError("pet description is invalid")
    if value.get("spritesheetPath") != "spritesheet.webp":
        raise ValueError("pet spritesheetPath must be spritesheet.webp")
    if "spriteVersionNumber" not in value:
        version = 1
    elif type(value["spriteVersionNumber"]) is int and value["spriteVersionNumber"] == 2:
        version = 2
    else:
        raise ValueError("spriteVersionNumber must be omitted for V1 or set to 2 for V2")

    rows = 9 if version == 1 else 11
    result = {
        "id": folder_name,
        "displayName": display_name.strip(),
        "description": description.strip(),
        "spritesheetPath": "spritesheet.webp",
        "spriteVersionNumber": version,
        "version": version,
        "frameWidth": 192,
        "frameHeight": 208,
        "columns": 8,
        "rows": rows,
        "rowCount": rows,
        "sheetWidth": 192 * 8,
        "sheetHeight": 208 * rows,
        "neutralIdleCell": {"row": 0, "column": 6} if version == 2 else None,
    }
    return result


MAX_SPRITESHEET_BYTES = 100 * 1024 * 1024
MAX_DECODED_PIXELS = 50_000_000
MAX_SPRITE_DIMENSION = 8192


def inspect_webp_header(header, file_size):
    """Read dimensions/animation flags from a bounded WebP container prefix."""
    if not isinstance(header, bytes) or len(header) < 12:
        raise ValueError("spritesheet is not a valid WebP container")
    if type(file_size) is not int or not 12 <= file_size <= MAX_SPRITESHEET_BYTES:
        raise ValueError("spritesheet size is invalid")
    if header[:4] != b"RIFF" or header[8:12] != b"WEBP":
        raise ValueError("spritesheet is not WebP")
    if int.from_bytes(header[4:8], "little") + 8 != file_size:
        raise ValueError("WebP container size does not match file size")

    width = height = None
    has_alpha = False
    animated = False
    offset = 12
    chunk_count = 0
    while offset + 8 <= len(header) and offset + 8 <= file_size:
        chunk_count += 1
        if chunk_count > 1024:
            raise ValueError("WebP has too many chunks")
        chunk_type = header[offset : offset + 4]
        chunk_size = int.from_bytes(header[offset + 4 : offset + 8], "little")
        payload = offset + 8
        end = payload + chunk_size
        padded_end = end + (chunk_size & 1)
        if end > file_size or padded_end > file_size:
            raise ValueError("WebP chunk exceeds container bounds")

        if chunk_type == b"VP8X":
            if chunk_size < 10 or payload + 10 > len(header):
                raise ValueError("WebP extended header is truncated")
            flags = header[payload]
            width = 1 + int.from_bytes(header[payload + 4 : payload + 7], "little")
            height = 1 + int.from_bytes(header[payload + 7 : payload + 10], "little")
            has_alpha = bool(flags & 0x10)
            animated = bool(flags & 0x02)
        elif chunk_type == b"VP8 " and width is None:
            if chunk_size < 10 or payload + 10 > len(header):
                raise ValueError("WebP image header is truncated")
            if header[payload + 3 : payload + 6] != b"\x9d\x01\x2a":
                raise ValueError("WebP lossy frame header is invalid")
            width = int.from_bytes(header[payload + 6 : payload + 8], "little") & 0x3FFF
            height = int.from_bytes(header[payload + 8 : payload + 10], "little") & 0x3FFF
        elif chunk_type == b"VP8L" and width is None:
            if chunk_size < 5 or payload + 5 > len(header) or header[payload] != 0x2F:
                raise ValueError("WebP lossless frame header is invalid")
            b1, b2, b3, b4 = header[payload + 1 : payload + 5]
            width = 1 + b1 + ((b2 & 0x3F) << 8)
            height = 1 + (b2 >> 6) + (b3 << 2) + ((b4 & 0x0F) << 10)
            has_alpha = bool(b4 & 0x10)
        elif chunk_type == b"ALPH":
            has_alpha = True
        elif chunk_type in (b"ANIM", b"ANMF"):
            animated = True

        offset = padded_end
        if offset > len(header):
            break

    if width is None or height is None or width <= 0 or height <= 0:
        raise ValueError("WebP dimensions were not found in the bounded header")
    return {
        "width": width,
        "height": height,
        "hasAlpha": has_alpha,
        "animated": animated,
    }


def validate_spritesheet(metadata, image_info, file_size):
    """Enforce bounded, version-specific atlas geometry before QML decoding."""
    if not isinstance(image_info, dict):
        raise ValueError("spritesheet header is invalid")
    width = image_info.get("width")
    height = image_info.get("height")
    if type(width) is not int or type(height) is not int:
        raise ValueError("spritesheet dimensions are invalid")
    if not 0 < width <= MAX_SPRITE_DIMENSION or not 0 < height <= MAX_SPRITE_DIMENSION:
        raise ValueError("spritesheet dimensions exceed safe limits")
    if width * height > MAX_DECODED_PIXELS:
        raise ValueError("spritesheet decoded pixel count exceeds safe limits")
    if type(file_size) is not int or not 12 <= file_size <= MAX_SPRITESHEET_BYTES:
        raise ValueError("spritesheet size exceeds safe limits")
    if type(image_info.get("animated")) is not bool or image_info["animated"]:
        raise ValueError("animated spritesheets are not supported")

    columns = 8
    rows = metadata.get("rowCount") if isinstance(metadata, dict) else None
    if type(rows) is not int or rows not in (9, 11):
        raise ValueError("pet atlas version is invalid")
    if rows == 11:
        if (width, height) != (1536, 2288):
            raise ValueError("OpenPets V2 spritesheet dimensions must be 1536x2288")
        if image_info.get("hasAlpha") is not True:
            raise ValueError("OpenPets V2 spritesheet must use transparency")
    elif width % columns or height % rows or width // columns < 192 or height // rows < 208:
        raise ValueError("OpenPets V1 atlas must have at least 192x208 frames in an 8x9 grid")

    result = dict(metadata)
    result.update(
        {
            "sheetWidth": width,
            "sheetHeight": height,
            "frameWidth": width // columns,
            "frameHeight": height // rows,
            "columns": columns,
            "rows": rows,
            "fileSize": file_size,
        }
    )
    return result
