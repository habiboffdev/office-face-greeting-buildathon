"""Bootstrap the 5-person demo recognition seed set."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from recognition.seed import (
    DEFAULT_EXPECTED_SEED_COUNT,
    bootstrap_seed_set,
    discover_seed_people,
    load_seed_manifest,
)
from recognition.writer import NoFaceInImageError


def _load_config(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Register exactly 5 demo people from local face photos.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="CSV with name,image_path columns. Use this for real greeting names.",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=None,
        help="Folder of seed photos used when --manifest is omitted.",
    )
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--people-json", type=Path, default=None)
    parser.add_argument("--faces-dir", type=Path, default=None)
    parser.add_argument("--expected-count", type=int, default=DEFAULT_EXPECTED_SEED_COUNT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = _load_config(args.config)

    people_json = args.people_json or Path(config.get("people_db_path", "people.json"))
    faces_dir = args.faces_dir or Path(config.get("faces_folder", "faces"))
    source_dir = args.source_dir or faces_dir

    try:
        if args.manifest is not None:
            people = load_seed_manifest(args.manifest)
        else:
            people = discover_seed_people(source_dir, expected_count=args.expected_count)

        registry = bootstrap_seed_set(
            people,
            people_json_path=people_json,
            faces_dir=faces_dir,
            expected_count=args.expected_count,
        )
    except NoFaceInImageError as exc:
        print(f"Error: no face detected: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Seeded {len(registry.names)} people into {people_json}")
    for name in registry.names:
        print(f"- {name}")
    if args.manifest is None:
        print("Tip: use --manifest with name,image_path columns before the demo for real names.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
