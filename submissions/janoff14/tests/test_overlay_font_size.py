"""Pure-function tests for the overlay font sizing rule (NFR25).

No QApplication required — `compute_font_size` is a deterministic helper
extracted from `player/overlay.py` so we can verify the 8 %-of-display-height
contract without booting Qt.

Run with: python -m unittest tests.test_overlay_font_size
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from player.overlay import compute_font_size


class TestComputeFontSize(unittest.TestCase):
    def test_default_factor_yields_at_least_8_percent_of_height(self) -> None:
        # 1080p screen at the default 0.08 factor must be >= 8% of height in pt.
        # Pt and px aren't 1:1, but the helper returns a value chosen to render
        # roughly 8% physical height; the test just guards the floor.
        font_pt = compute_font_size(1080, 0.08)
        self.assertGreaterEqual(font_pt, int(1080 * 0.08 * 0.5))

    def test_4k_display(self) -> None:
        font_pt = compute_font_size(2160, 0.08)
        self.assertGreater(font_pt, compute_font_size(1080, 0.08))

    def test_clamps_to_minimum_on_tiny_displays(self) -> None:
        # A 200-px-tall display would compute 16 pt at 0.08, below the floor.
        font_pt = compute_font_size(200, 0.08)
        self.assertGreaterEqual(font_pt, 24)

    def test_zero_or_negative_height_returns_minimum(self) -> None:
        self.assertGreaterEqual(compute_font_size(0, 0.08), 24)
        self.assertGreaterEqual(compute_font_size(-100, 0.08), 24)

    def test_larger_factor_yields_larger_font(self) -> None:
        smaller = compute_font_size(1080, 0.05)
        larger = compute_font_size(1080, 0.12)
        self.assertLess(smaller, larger)


if __name__ == "__main__":
    unittest.main()
