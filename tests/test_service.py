from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from relay_ssh.models import Handoff, RelayConfig
from relay_ssh.service import RelayService
from relay_ssh.state import StateStore


class FakeGitHub:
    def __init__(self) -> None:
        self.pending: list[Handoff] = []
        self.labels: dict[int, bool] = {}

    def pending_handoffs(self, label: str, processed_event_ids: set[int]) -> list[Handoff]:
        return [item for item in self.pending if item.event_id not in processed_event_ids]

    def issue_has_label(self, issue_number: int, label: str) -> bool:
        return self.labels.get(issue_number, False)


class FakeAdapter:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.delivered: list[tuple[Handoff, str]] = []

    def deliver(self, handoff: Handoff, prompt: str) -> None:
        if self.fail:
            raise RuntimeError("delivery failed")
        self.delivered.append((handoff, prompt))


def handoff(event_id: int = 100, issue_number: int = 3) -> Handoff:
    return Handoff(
        repository="owner/repo",
        issue_number=issue_number,
        issue_title="Task",
        issue_url=f"https://github.com/owner/repo/issues/{issue_number}",
        event_id=event_id,
        event_created_at="2026-08-29T00:00:00Z",
        target_label="relay:codex",
    )


class ServiceTest(unittest.TestCase):
    def make_service(self, temp_dir: str, github: FakeGitHub, adapter: FakeAdapter):
        config = RelayConfig(repository="owner/repo", adapter="stdout")
        store = StateStore(Path(temp_dir) / "state.json")
        service = RelayService(config, github, adapter, store, logger=lambda _: None)
        return service, store

    def test_delivers_once_and_waits_for_label_transition(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            github = FakeGitHub()
            github.pending = [handoff()]
            github.labels[3] = True
            adapter = FakeAdapter()
            service, store = self.make_service(temp_dir, github, adapter)

            first = service.poll_once()
            self.assertEqual(first.status, "delivered")
            self.assertEqual(len(adapter.delivered), 1)

            second = service.poll_once()
            self.assertEqual(second.status, "waiting-for-owner-transition")
            self.assertEqual(len(adapter.delivered), 1)

            github.labels[3] = False
            third = service.poll_once()
            self.assertEqual(third.status, "idle")
            self.assertIsNone(store.load().inflight)

    def test_failed_delivery_is_not_marked_processed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            github = FakeGitHub()
            github.pending = [handoff()]
            adapter = FakeAdapter(fail=True)
            service, store = self.make_service(temp_dir, github, adapter)

            with self.assertRaisesRegex(RuntimeError, "delivery failed"):
                service.poll_once()
            state = store.load()
            self.assertEqual(state.processed_event_ids, [])
            self.assertIsNone(state.inflight)

    def test_pause_prevents_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            github = FakeGitHub()
            github.pending = [handoff()]
            adapter = FakeAdapter()
            service, store = self.make_service(temp_dir, github, adapter)
            state = store.load()
            state.paused = True
            store.save(state)

            result = service.poll_once()
            self.assertEqual(result.status, "paused")
            self.assertEqual(adapter.delivered, [])


if __name__ == "__main__":
    unittest.main()
