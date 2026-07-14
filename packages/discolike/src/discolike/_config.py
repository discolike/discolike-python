from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from discolike._exceptions import AuthenticationError

DEFAULT_BASE_URL = "https://api.discolike.com/v1"
ENV_API_KEY = "DISCOLIKE_API_KEY"  # foxguard: ignore[py/no-hardcoded-secret]
KEYS_URL = "https://app.discolike.com/account/management/keys"

_NO_KEY_MESSAGE = (
    "No API key found. Set the DISCOLIKE_API_KEY environment variable, pass api_key=..., "
    f"or run `discolike auth login`. Create a key at {KEYS_URL}"
)


def config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "discolike" / "config.json"


def load_config() -> dict[str, Any]:
    path = config_path()
    if not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text())
    except (ValueError, OSError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def save_config(config: dict[str, Any]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(json.dumps(config, indent=2) + "\n")
    path.chmod(0o600)


def delete_config() -> None:
    config_path().unlink(missing_ok=True)


def resolve_api_key(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    from_env = os.environ.get(ENV_API_KEY)
    if from_env:
        return from_env
    from_file = load_config().get("api_key")
    if from_file:
        return str(from_file)
    raise AuthenticationError(_NO_KEY_MESSAGE)
