#!/usr/bin/env python3
"""Small validated JSON boundary between Omarchy's hosted QML and local files.

The shell invokes this script with -I and fixed argv; it never sources code from
Hermes profile directories or executes strings from local configuration.
"""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.omapets_data import discover_profile_homes, load_profile_config, write_profile_config
from scripts.omapets_runtime import build_snapshot


def run(argv=None):
    parser = argparse.ArgumentParser(description="OmaPets local snapshot and configuration")
    parser.add_argument("--root", type=Path, default=Path.home() / ".hermes")
    parser.add_argument("--defaults", type=Path, default=Path(__file__).resolve().parents[1] / "phrases")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("snapshot")
    setter = subcommands.add_parser("set")
    setter.add_argument("profile")
    setter.add_argument("field", choices=("enabled", "petId", "mode", "speed", "position", "screen", "scale"))
    setter.add_argument("value")
    args = parser.parse_args(argv)

    if args.command == "snapshot":
        result = build_snapshot(args.root, args.defaults)
    else:
        profiles = dict(discover_profile_homes(args.root))
        if args.profile not in profiles:
            raise ValueError("unknown local Hermes profile")
        home = profiles[args.profile]
        config, error = load_profile_config(home)
        if error:
            raise ValueError("existing profile configuration is invalid; repair it before editing")
        value = args.value
        if args.field == "enabled":
            if value not in ("true", "false"):
                raise ValueError("enabled must be true or false")
            if value == "true" and not config["petId"]:
                available = build_snapshot(args.root, args.defaults)["petIds"]
                if not available:
                    raise ValueError("no valid local OpenPets characters available")
                config["petId"] = available[0]
            config["enabled"] = value == "true"
        elif args.field == "petId":
            if value not in build_snapshot(args.root, args.defaults)["petIds"]:
                raise ValueError("character is not a valid installed OpenPets package")
            config["petId"] = value
        elif args.field == "mode":
            config["mode"] = value
        elif args.field == "speed":
            config["speed"] = value
        elif args.field == "position":
            try:
                x, y = value.split(",")
                config["position"] = {"x": float(x), "y": float(y)}
            except (ValueError, TypeError) as exc:
                raise ValueError("position must be x,y fractions") from exc
        elif args.field == "scale":
            if not value.isascii() or not value.isdecimal():
                raise ValueError("scale must be an integer")
            config["scale"] = int(value)
        else:
            config["screen"] = value
        write_profile_config(home, config)
        result = {"ok": True, "profile": args.profile}
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except (OSError, ValueError) as exc:
        print("OmaPets: " + str(exc)[:160], file=sys.stderr)
        raise SystemExit(2) from None
