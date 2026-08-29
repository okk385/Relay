from __future__ import annotations

import unittest

from relay_ssh.github import latest_label_event


class GitHubHelpersTest(unittest.TestCase):
    def test_latest_label_event_uses_event_id(self) -> None:
        events = [
            {"id": 10, "event": "labeled", "label": {"name": "relay:codex"}},
            {"id": 11, "event": "unlabeled", "label": {"name": "relay:codex"}},
            {"id": 12, "event": "labeled", "label": {"name": "other"}},
            {"id": 13, "event": "labeled", "label": {"name": "relay:codex"}},
        ]
        event = latest_label_event(events, "relay:codex")
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event["id"], 13)

    def test_latest_label_event_returns_none(self) -> None:
        self.assertIsNone(latest_label_event([], "relay:codex"))


if __name__ == "__main__":
    unittest.main()
