from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from relay_ssh.state import RelayState, StateStore


class StateStoreTest(unittest.TestCase):
    def test_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = StateStore(Path(temp_dir) / "state.json")
            state = RelayState(
                processed_event_ids=[1, 2],
                paused=True,
                inflight={"event_id": 2, "issue_number": 7, "target_label": "relay:codex"},
            )
            store.save(state)
            loaded = store.load()
            self.assertEqual(loaded.processed_event_ids, [1, 2])
            self.assertTrue(loaded.paused)
            self.assertEqual(loaded.inflight["issue_number"], 7)

    def test_missing_state_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = StateStore(Path(temp_dir) / "missing.json")
            self.assertEqual(store.load().processed_event_ids, [])


if __name__ == "__main__":
    unittest.main()
