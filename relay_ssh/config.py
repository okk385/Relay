from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .models import RelayConfig


def config_home() -> Path:
    root = os.environ.get("XDG_CONFIG_HOME")
    return Path(root).expanduser() if root else Path.home() / ".config"


def state_home() -> Path:
    root = os.environ.get("XDG_STATE_HOME")
    return Path(root).expanduser() if root else Path.home() / ".local" / "state"


def default_config_path() -> Path:
    return config_home() / "relay" / "config.json"


def default_state_path() -> Path:
    return state_home() / "relay" / "state.json"


def load_config(path: Path | None = None) -> RelayConfig:
    target = (path or default_config_path()).expanduser()
    try:
        raw: dict[str, Any] = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Relay config not found at {target}. Run `relay init` first."
        ) from exc
    config = RelayConfig.from_dict(raw)
    if config.state_path is None:
        config.state_path = str(default_state_path())
    return config


def save_config(config: RelayConfig, path: Path | None = None) -> Path:
    target = (path or default_config_path()).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload = config.to_dict()
    if payload.get("state_path") is None:
        payload["state_path"] = str(default_state_path())
    _atomic_write_json(target, payload)
    try:
        target.chmod(0o600)
    except OSError:
        pass
    return target


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)
