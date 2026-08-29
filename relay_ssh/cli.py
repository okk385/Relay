from __future__ import annotations

import argparse
import json
from dataclasses import asdict
import shlex
import sys
from pathlib import Path

from .adapters import build_adapter
from .config import default_config_path, default_state_path, load_config, save_config
from .github import GitHubClient, GitHubError, resolve_github_token
from .models import RelayConfig
from .service import RelayService
from .state import StateStore


def _config_path(value: str | None) -> Path:
    return Path(value).expanduser() if value else default_config_path()


def _make_runtime(config_path: Path):
    config = load_config(config_path)
    token = resolve_github_token()
    github = GitHubClient(config.repository, token)
    adapter = build_adapter(config)
    store = StateStore(Path(config.state_path or default_state_path()))
    service = RelayService(config, github, adapter, store)
    return config, github, store, service


def cmd_init(args: argparse.Namespace) -> int:
    command: list[str] = []
    if args.command:
        command = shlex.split(args.command)
    config = RelayConfig(
        repository=args.repo,
        poll_interval_seconds=args.poll_interval,
        target_label="relay:codex",
        adapter=args.adapter,
        tmux_target=args.tmux_target,
        command=command,
        workdir=args.workdir,
        state_path=args.state_path or str(default_state_path()),
    )
    path = save_config(config, _config_path(args.config))
    print(f"Wrote {path}")
    print("Token resolution: RELAY_GITHUB_TOKEN, GITHUB_TOKEN, or `gh auth token`.")
    if args.adapter == "stdout":
        print("Adapter is stdout (dry-run mode).")
    return 0


def cmd_once(args: argparse.Namespace) -> int:
    _config, _github, _store, service = _make_runtime(_config_path(args.config))
    result = service.poll_once()
    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    _config, _github, _store, service = _make_runtime(_config_path(args.config))
    service.run_forever()
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    config = load_config(_config_path(args.config))
    store = StateStore(Path(config.state_path or default_state_path()))
    state = store.load()
    print(
        json.dumps(
            {
                "repository": config.repository,
                "target_label": config.target_label,
                "adapter": config.adapter,
                "tmux_target": config.tmux_target,
                "command": config.command,
                "poll_interval_seconds": config.poll_interval_seconds,
                "state": state.to_dict(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _set_paused(args: argparse.Namespace, paused: bool) -> int:
    config = load_config(_config_path(args.config))
    store = StateStore(Path(config.state_path or default_state_path()))
    state = store.load()
    state.paused = paused
    store.save(state)
    print("Relay paused" if paused else "Relay resumed")
    return 0


def cmd_setup_labels(args: argparse.Namespace) -> int:
    config = load_config(_config_path(args.config))
    github = GitHubClient(config.repository, resolve_github_token())
    created = github.ensure_protocol_labels()
    present = github.verify_protocol_labels()
    print(f"Protocol labels present: {', '.join(sorted(present))}")
    if created:
        print(f"Created: {', '.join(created)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="relay",
        description="Git-native ChatGPT -> Codex handoff worker",
    )
    parser.add_argument("--config", help="path to Relay config JSON")
    subparsers = parser.add_subparsers(dest="command_name", required=True)

    init = subparsers.add_parser("init", help="write Relay configuration")
    init.add_argument("--repo", required=True, help="GitHub repository in owner/name form")
    init.add_argument(
        "--adapter",
        choices=("stdout", "tmux", "command"),
        default="stdout",
        help="handoff delivery adapter",
    )
    init.add_argument("--tmux-target", help="tmux target such as relay-codex:0.0")
    init.add_argument(
        "--command",
        help="command adapter argv as one shell-like string; prompt is sent on stdin",
    )
    init.add_argument("--workdir", help="working directory for the command adapter")
    init.add_argument("--poll-interval", type=int, default=30)
    init.add_argument("--state-path", help="override local state file")
    init.set_defaults(func=cmd_init)

    once = subparsers.add_parser("once", help="run one GitHub poll")
    once.set_defaults(func=cmd_once)

    start = subparsers.add_parser("start", help="run the polling worker")
    start.set_defaults(func=cmd_start)

    status = subparsers.add_parser("status", help="show config and local state")
    status.set_defaults(func=cmd_status)

    pause = subparsers.add_parser("pause", help="pause automatic handoffs")
    pause.set_defaults(func=lambda args: _set_paused(args, True))

    resume = subparsers.add_parser("resume", help="resume automatic handoffs")
    resume.set_defaults(func=lambda args: _set_paused(args, False))

    labels = subparsers.add_parser("setup-labels", help="create Relay protocol labels")
    labels.set_defaults(func=cmd_setup_labels)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (ValueError, FileNotFoundError, GitHubError) as exc:
        print(f"relay: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
