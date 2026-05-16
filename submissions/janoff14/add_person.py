"""CLI fallback for adding a registered person without Telegram (Story 4.1).

Usage::

    python add_person.py "<name>" <image_path>

Reuses ``recognition.writer.add_person`` so the CLI and the Telegram bot
share one code path (AR9). Works fully offline — no network calls. The
recognition worker picks up the new entry within 5 s via Story 3.5's
file-watcher hot reload.

Exit codes:
* 0 — success
* 1 — usage error (missing args)
* 2 — operational error (image missing, no face, decode failure)
"""

from __future__ import annotations

import sys
import argparse
from pathlib import Path

from bot import load_config
from recognition.writer import NoFaceInImageError, add_person


def main(argv: list[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if len(raw_args) < 2:
        print('Usage: python add_person.py "<name>" <image_path>', file=sys.stderr)
        return 1
    parser = argparse.ArgumentParser(description="Add or update a registered person.")
    parser.add_argument("name")
    parser.add_argument("image_path")
    parser.add_argument("--language", choices=["en", "uz", "ru"], default=None)
    parser.add_argument("--birthday", default=None, help="Optional MM-DD birthday")
    parser.add_argument("--custom-message", default=None)
    parsed = parser.parse_args(raw_args)

    name, image_arg = parsed.name, parsed.image_path
    image_path = Path(image_arg)
    if not image_path.exists():
        print(f"Error: image file not found: {image_arg}", file=sys.stderr)
        return 2

    config = load_config()
    people_db_path = Path(config.get("people_db_path", "people.json"))
    faces_folder = Path(config.get("faces_folder", "faces"))

    try:
        add_person(
            name,
            image_path,
            people_db_path,
            faces_folder,
            language=parsed.language,
            birthday=parsed.birthday,
            custom_message=parsed.custom_message,
        )
    except NoFaceInImageError:
        print(f"Error: no face detected in {image_arg}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"Error: image file not found: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print(f"Added: {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
