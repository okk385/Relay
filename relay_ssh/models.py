from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

OWNER_LABELS = (
    "relay:codex",
    "relay:chatgpt",
    "relay:human",
    "relay:done",
)


def validate_repository(value: str) -> str:
    value = value.strip()
    parts = value.split("/")
    if len(parts) != 2 or not all(parts):
        raise ValueError("repository must use owner/name form")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
    if any(set(part) - allowed for part in parts):
        raise ValueError("repository contains unsupported characters")
    return value


@dataclass(slots=True, frozen=True)
class Handoff:
    repository: str
    issue_number: int
    issue_title: str
    issue_url: str
    event_id: int
    event_created_at: str
    target_label: str

    @property
    def dedupe_key(self) -> str:
        return f"github-label-event:{self.event_id}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "repository": self.repository,
            "issue_number": self.issue_number,
            "issue_title": self.issue_title,
            "issue_url": self.issue_url,
            "event_id": self.event_id,
            "event_created_at": self.event_created_at,
            "target_label": self.target_label,
        }


@dataclass(slots=True)
class RelayConfig:
    repository: str
    poll_interval_seconds: int = 30
    target_label: str = "relay:codex"
    adapter: str = "stdout"
    tmux_target: str | None = None
    command: list[str] = field(default_factory=list)
    workdir: str | None = None
    state_path: str | None = None

    def __post_init__(self) -> None:
        self.repository = validate_repository(self.repository)
        if self.poll_interval_seconds < 5:
            raise ValueError("poll_interval_seconds must be at least 5")
        if self.target_label not in OWNER_LABELS:
            raise ValueError(f"unsupported target label: {self.target_label}")
        if self.adapter not in {"stdout", "tmux", "command"}:
            raise ValueError("adapter must be stdout, tmux, or command")
        if self.adapter == "tmux" and not self.tmux_target:
            raise ValueError("tmux adapter requires tmux_target")
        if self.adapter == "command" and not self.command:
            raise ValueError("command adapter requires a command")
        if self.workdir:
            self.workdir = str(Path(self.workdir).expanduser().resolve())

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "RelayConfig":
        return cls(
            repository=str(raw["repository"]),
            poll_interval_seconds=int(raw.get("poll_interval_seconds", 30)),
            target_label=str(raw.get("target_label", "relay:codex")),
            adapter=str(raw.get("adapter", "stdout")),
            tmux_target=raw.get("tmux_target"),
            command=[str(item) for item in raw.get("command", [])],
            workdir=raw.get("workdir"),
            state_path=raw.get("state_path"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "repository": self.repository,
            "poll_interval_seconds": self.poll_interval_seconds,
            "target_label": self.target_label,
            "adapter": self.adapter,
            "tmux_target": self.tmux_target,
            "command": list(self.command),
            "workdir": self.workdir,
            "state_path": self.state_path,
        }


def build_codex_prompt(handoff: Handoff) -> str:
    return "\n".join(
        [
            "RELAY HANDOFF — CHATGPT TO CODEX",
            "",
            f"Repository: {handoff.repository}",
            f"Issue: #{handoff.issue_number} — {handoff.issue_title}",
            f"URL: {handoff.issue_url}",
            f"Handoff event: {handoff.event_id}",
            "",
            "Read the GitHub issue and repository, then execute the task according to its instructions.",
            "Relay does not manage your implementation or experiment workflow.",
            "",
            "When your part is complete, report code/results/artifacts on GitHub, remove `relay:codex`,",
            "and add exactly one next-owner label:",
            "- `relay:chatgpt` for review or planning",
            "- `relay:human` for a human decision",
            "- `relay:done` if the task is complete.",
        ]
    )
