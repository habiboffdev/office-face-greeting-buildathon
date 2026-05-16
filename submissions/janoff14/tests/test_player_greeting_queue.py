"""Tests for the player-side greeting queue drain helper."""

from __future__ import annotations

import queue
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from player.greeting_queue import drain_greeting_queue


class TestDrainGreetingQueue(unittest.TestCase):
    def test_drains_valid_events_in_order(self) -> None:
        greeting_queue = queue.Queue()
        greeting_queue.put({"name": "Alice", "timestamp": 1.0})
        greeting_queue.put({"name": "Bob", "timestamp": 2.0})
        names: list[str] = []

        handled = drain_greeting_queue(greeting_queue, names.append)

        self.assertEqual(handled, 2)
        self.assertEqual(names, ["Alice", "Bob"])

    def test_ignores_invalid_events_without_blocking(self) -> None:
        greeting_queue = queue.Queue()
        greeting_queue.put({"name": ""})
        greeting_queue.put({"name": None})
        greeting_queue.put("not a dict")
        greeting_queue.put({"name": " Aziza "})
        names: list[str] = []

        handled = drain_greeting_queue(greeting_queue, names.append)

        self.assertEqual(handled, 1)
        self.assertEqual(names, ["Aziza"])

    def test_respects_max_events_per_poll(self) -> None:
        greeting_queue = queue.Queue()
        greeting_queue.put({"name": "One"})
        greeting_queue.put({"name": "Two"})
        names: list[str] = []

        handled = drain_greeting_queue(greeting_queue, names.append, max_events=1)

        self.assertEqual(handled, 1)
        self.assertEqual(names, ["One"])
        self.assertFalse(greeting_queue.empty())


if __name__ == "__main__":
    unittest.main()
