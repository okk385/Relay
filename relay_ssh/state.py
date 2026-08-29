from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class RelayState:
    processed_event_ids: list[int] = field(default_factory=list)
    paused: bool = False
    inflight: dict[str, Any] | None = None
    last_poll_at: str | None = None
    last_delivery_at: str | None = None
    last_error: str | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "RelayState":
        return cls(
            processed_event_ids=[int(item) for item in raw.get("processed_event_ids", [])],
            paused=bool(raw.get("paused", False)),
            inflight=raw.get("inflight"),
            last_poll_at=raw.get("last_poll_at"),
            last_delivery_at=raw.get("last_delivery_at"),
            last_error=raw.get("last_error"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "processed_event_ids": self.processed_event_ids[-2000:],
            "paused": self.paused,
            "inflight": self.inflight,
            "last_poll_at": self.last_poll_at,
            "last_delivery_at": self.last_delivery_at,
            "last_error": self.last_error,
        }


class StateStore:
    def __init__(self, path: Path):
        self.path = path.expanduser()

    def load(self) -> RelayState:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return RelayState()
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid Relay state file: {self.path}") from exc
        return RelayState.from_dict(raw)

    def save(self, state: RelayState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(
            json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temp, self.path)
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def update(self, mutator) -> RelayState:
        state = self.load()
        mutator(state)
        self.save(state)
        return state
