"""CLI fallback for adding a promo video without Telegram (Story 4.2).

Usage::

    python add_video.py <video_path>

Reuses ``player.video_writer.add_video`` so the CLI and the Telegram bot
share one atomic-copy code path (AR9). No file-size limit — this is the
explicit reason this CLI exists alongside the 20 MB bot path. Works
fully offline. The player picks up the new video at the end of the
current playback iteration (Story 3.7's rescan).

Exit codes:
* 0 — success
* 1 — usage error (missing args)
* 2 — operational error (source missing, unsupported extension)
"""

from __future__ import annotations

import sys
from pathlib import Path

from bot import load_config
from player.playlist import scan_playlist
from player.video_writer import UnsupportedVideoFormatError, add_video


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("Usage: python add_video.py <video_path>", file=sys.stderr)
        return 1

    source_arg = args[0]
    source_path = Path(source_arg)
    if not source_path.exists():
        print(f"Error: video file not found: {source_arg}", file=sys.stderr)
        return 2

    config = load_config()
    video_folder = Path(config.get("video_folder", "videos"))

    try:
        final = add_video(source_path, video_folder)
    except UnsupportedVideoFormatError as exc:
        print(
            f"Error: unsupported video format: {exc.extension}. Use .mp4, .mov, or .webm.",
            file=sys.stderr,
        )
        return 2
    except FileNotFoundError:
        print(f"Error: video file not found: {source_arg}", file=sys.stderr)
        return 2

    count = len(scan_playlist(video_folder))
    print(f"Added: {final.name}. Playlist now has {count} videos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
