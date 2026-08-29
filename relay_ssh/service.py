from __future__ import annotations

import signal
import time
from dataclasses import dataclass
from typing import Callable

from .adapters import DeliveryAdapter
from .github import GitHubClient
from .models import RelayConfig, build_codex_prompt
from .state import RelayState, StateStore, utc_now


@dataclass(slots=True, frozen=True)
class PollResult:
    status: str
    issue_number: int | None = None
    event_id: int | None = None
    detail: str | None = None


class RelayService:
    def __init__(
        self,
        config: RelayConfig,
        github: GitHubClient,
        adapter: DeliveryAdapter,
        store: StateStore,
        *,
        logger: Callable[[str], None] = print,
    ):
        self.config = config
        self.github = github
        self.adapter = adapter
        self.store = store
        self.logger = logger
        self._stop = False

    def _save_error(self, state: RelayState, message: str) -> None:
        state.last_poll_at = utc_now()
        state.last_error = message
        self.store.save(state)

    def poll_once(self) -> PollResult:
        state = self.store.load()
        state.last_poll_at = utc_now()

        if state.paused:
            state.last_error = None
            self.store.save(state)
            return PollResult("paused")

        if state.inflight:
            issue_number = int(state.inflight["issue_number"])
            label = str(state.inflight["target_label"])
            if self.github.issue_has_label(issue_number, label):
                state.last_error = None
                self.store.save(state)
                return PollResult(
                    "waiting-for-owner-transition",
                    issue_number=issue_number,
                    event_id=int(state.inflight["event_id"]),
                )
            state.inflight = None

        pending = self.github.pending_handoffs(
            self.config.target_label,
            set(state.processed_event_ids),
        )
        if not pending:
            state.last_error = None
            self.store.save(state)
            return PollResult("idle")

        handoff = pending[0]
        prompt = build_codex_prompt(handoff)
        try:
            self.adapter.deliver(handoff, prompt)
        except Exception as exc:
            self._save_error(state, str(exc))
            raise

        state.processed_event_ids.append(handoff.event_id)
        state.processed_event_ids = state.processed_event_ids[-2000:]
        state.inflight = {
            "event_id": handoff.event_id,
            "issue_number": handoff.issue_number,
            "target_label": handoff.target_label,
            "delivered_at": utc_now(),
        }
        state.last_delivery_at = utc_now()
        state.last_error = None
        self.store.save(state)
        return PollResult(
            "delivered",
            issue_number=handoff.issue_number,
            event_id=handoff.event_id,
        )

    def stop(self, *_args) -> None:
        self._stop = True

    def run_forever(self) -> None:
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)
        self.logger(
            f"Relay connected to {self.config.repository}; polling "
            f"{self.config.target_label} every {self.config.poll_interval_seconds}s"
        )
        while not self._stop:
            try:
                result = self.poll_once()
                if result.status == "delivered":
                    self.logger(
                        f"ChatGPT -> Codex: issue #{result.issue_number} "
                        f"(event {result.event_id})"
                    )
            except Exception as exc:
                self.logger(f"Relay poll failed: {exc}")
            if not self._stop:
                time.sleep(self.config.poll_interval_seconds)
        self.logger("Relay stopped")
