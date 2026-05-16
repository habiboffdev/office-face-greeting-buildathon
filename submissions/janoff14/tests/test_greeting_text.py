"""Tests for player.greeting_text (Story 5.1)."""

from __future__ import annotations

import random
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from player.greeting_text import (
    DEFAULT_FALLBACK,
    TIME_BAND_TEMPLATES,
    band_for_hour,
    build_greeting,
    holiday_for_date,
)


class BandForHourTests(unittest.TestCase):
    def test_late_wraps_midnight(self) -> None:
        for hour in (22, 23, 0, 1, 2, 3, 4):
            self.assertEqual(band_for_hour(hour), "late", f"hour={hour}")

    def test_morning(self) -> None:
        for hour in (5, 8, 11):
            self.assertEqual(band_for_hour(hour), "morning")

    def test_afternoon(self) -> None:
        for hour in (12, 14, 16):
            self.assertEqual(band_for_hour(hour), "afternoon")

    def test_evening(self) -> None:
        for hour in (17, 19, 21):
            self.assertEqual(band_for_hour(hour), "evening")


class HolidayForDateTests(unittest.TestCase):
    def test_matches_mmdd(self) -> None:
        holidays = {"03-21": "Navruz mubarak", "01-01": "Happy New Year"}
        self.assertEqual(holiday_for_date("2026-03-21T10:00:00", holidays), "Navruz mubarak")
        self.assertEqual(holiday_for_date("2026-01-01T00:00:00", holidays), "Happy New Year")

    def test_no_match_returns_none(self) -> None:
        self.assertIsNone(holiday_for_date("2026-07-04T10:00:00", {"03-21": "Navruz"}))

    def test_none_or_empty_holidays(self) -> None:
        self.assertIsNone(holiday_for_date("2026-03-21T10:00:00", None))
        self.assertIsNone(holiday_for_date("2026-03-21T10:00:00", {}))


class BuildGreetingTests(unittest.TestCase):
    def test_morning_default(self) -> None:
        line = build_greeting("Alice", now=datetime(2026, 5, 16, 9, 0))
        self.assertEqual(line, "Good morning, Alice!")

    def test_afternoon_default(self) -> None:
        line = build_greeting("Bob", now=datetime(2026, 5, 16, 14, 0))
        self.assertEqual(line, "Good afternoon, Bob!")

    def test_evening_default(self) -> None:
        line = build_greeting("Carol", now=datetime(2026, 5, 16, 19, 0))
        self.assertEqual(line, "Good evening, Carol!")

    def test_late_default(self) -> None:
        line = build_greeting("Dave", now=datetime(2026, 5, 16, 23, 30))
        self.assertEqual(line, "Still here, Dave?")

    def test_holiday_overrides_time_band(self) -> None:
        holidays = {"03-21": "Navruz mubarak"}
        line = build_greeting("Alice", now=datetime(2026, 3, 21, 9, 0), holidays=holidays)
        self.assertEqual(line, "Navruz mubarak, Alice!")

    def test_holiday_with_name_token_inline(self) -> None:
        holidays = {"01-01": "Happy New Year {name}"}
        line = build_greeting("Alice", now=datetime(2026, 1, 1, 12, 0), holidays=holidays)
        self.assertEqual(line, "Happy New Year Alice")

    def test_flavor_appended_with_separator(self) -> None:
        rng = random.Random(0)
        line = build_greeting(
            "Alice",
            now=datetime(2026, 5, 16, 9, 0),
            flavors=["nice scarf today"],
            rng=rng,
        )
        self.assertEqual(line, "Good morning, Alice! - nice scarf today")

    def test_flavor_with_name_token_inline(self) -> None:
        rng = random.Random(0)
        line = build_greeting(
            "Alice",
            now=datetime(2026, 5, 16, 9, 0),
            flavors=["coffee on me, {name}?"],
            rng=rng,
        )
        self.assertEqual(line, "Good morning, Alice! coffee on me, Alice?")

    def test_empty_flavor_list_skips_silently(self) -> None:
        line = build_greeting("Alice", now=datetime(2026, 5, 16, 9, 0), flavors=[])
        self.assertEqual(line, "Good morning, Alice!")

    def test_deterministic_with_seeded_rng(self) -> None:
        flavors = ["a", "b", "c", "d", "e"]
        rng1 = random.Random(42)
        rng2 = random.Random(42)
        line1 = build_greeting("Alice", now=datetime(2026, 5, 16, 9, 0), flavors=flavors, rng=rng1)
        line2 = build_greeting("Alice", now=datetime(2026, 5, 16, 9, 0), flavors=flavors, rng=rng2)
        self.assertEqual(line1, line2)

    def test_empty_name_falls_back_to_friend(self) -> None:
        line = build_greeting("", now=datetime(2026, 5, 16, 9, 0))
        self.assertEqual(line, "Good morning, friend!")

    def test_uzbek_language(self) -> None:
        line = build_greeting("Aziza", now=datetime(2026, 5, 16, 9, 0), language="uz")
        self.assertEqual(line, "Xayrli tong, Aziza!")

    def test_russian_language(self) -> None:
        line = build_greeting("Aziza", now=datetime(2026, 5, 16, 19, 0), language="ru")
        self.assertEqual(line, "Dobryy vecher, Aziza!")

    def test_birthday_overrides_time_and_holiday(self) -> None:
        line = build_greeting(
            "Alice",
            now=datetime(2026, 5, 16, 9, 0),
            birthday="05-16",
            holidays={"05-16": "Holiday"},
        )
        self.assertEqual(line, "Happy birthday, Alice!")

    def test_custom_message_overrides_flavor(self) -> None:
        line = build_greeting(
            "Alice",
            now=datetime(2026, 5, 16, 9, 0),
            custom_message="demo time",
            flavors=["ignored"],
        )
        self.assertEqual(line, "Good morning, Alice! - demo time")


if __name__ == "__main__":
    unittest.main()
