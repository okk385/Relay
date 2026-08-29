from __future__ import annotations

import shlex
import subprocess
import sys
import uuid
from dataclasses import dataclass
from typing import Protocol

from .models import Handoff, RelayConfig


class DeliveryError(RuntimeError):
    pass


class DeliveryAdapter(Protocol):
    def deliver(self, handoff: Handoff, prompt: str) -> None: ...


@dataclass(slots=True)
class StdoutAdapter:
    stream: object = sys.stdout

    def deliver(self, handoff: Handoff, prompt: str) -> None:
        print("\n" + "=" * 72, file=self.stream)
        print(prompt, file=self.stream)
        print("=" * 72, file=self.stream, flush=True)


@dataclass(slots=True)
class CommandAdapter:
    command: list[str]
    workdir: str | None = None

    def deliver(self, handoff: Handoff, prompt: str) -> None:
        if not self.command:
            raise DeliveryError("command adapter has no command")
        try:
            result = subprocess.run(
                self.command,
                input=prompt,
                text=True,
                cwd=self.workdir,
                check=False,
            )
        except OSError as exc:
            raise DeliveryError(f"failed to start {shlex.join(self.command)}: {exc}") from exc
        if result.returncode != 0:
            raise DeliveryError(
                f"delivery command exited with status {result.returncode}: {shlex.join(self.command)}"
            )


@dataclass(slots=True)
class TmuxAdapter:
    target: str

    def _run(self, args: list[str], *, input_text: str | None = None) -> None:
        try:
            result = subprocess.run(
                ["tmux", *args],
                input=input_text,
                text=True,
                capture_output=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise DeliveryError("tmux is not installed or not on PATH") from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise DeliveryError(f"tmux {' '.join(args)} failed: {detail}")

    def deliver(self, handoff: Handoff, prompt: str) -> None:
        self._run(["display-message", "-p", "-t", self.target, "#{pane_id}"])
        buffer_name = f"relay-{handoff.event_id}-{uuid.uuid4().hex[:8]}"
        self._run(["load-buffer", "-b", buffer_name, "-"], input_text=prompt)
        try:
            self._run(["paste-buffer", "-b", buffer_name, "-d", "-t", self.target])
            self._run(["send-keys", "-t", self.target, "Enter"])
        except DeliveryError:
            subprocess.run(
                ["tmux", "delete-buffer", "-b", buffer_name],
                capture_output=True,
                check=False,
            )
            raise


def build_adapter(config: RelayConfig) -> DeliveryAdapter:
    if config.adapter == "stdout":
        return StdoutAdapter()
    if config.adapter == "tmux":
        assert config.tmux_target is not None
        return TmuxAdapter(config.tmux_target)
    if config.adapter == "command":
        return CommandAdapter(config.command, config.workdir)
    raise ValueError(f"unsupported adapter: {config.adapter}")
