from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from discolike._credentials import ApiKeyCredential
from discolike._credentials import Credential
from discolike._credentials import OAuthClientRegistration
from discolike._credentials import OAuthCredential
from discolike._exceptions import AuthenticationError

DEFAULT_BASE_URL = "https://api.discolike.com/v1"
ENV_API_KEY = "DISCOLIKE_API_KEY"  # foxguard: ignore[py/no-hardcoded-secret]
KEYS_URL = "https://app.discolike.com/account/management/keys"
AUTH_METHOD_API_KEY = "api_key"
AUTH_METHOD_OAUTH = "oauth"
OAUTH_CLIENT_KEY = "oauth_client"

NO_CREDENTIAL_MESSAGE = (
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
    fd, temp_path = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    with os.fdopen(fd, "w") as handle:
        handle.write(json.dumps(config, indent=2) + "\n")
    os.chmod(temp_path, 0o600)
    os.replace(temp_path, path)


def delete_config() -> None:
    config_path().unlink(missing_ok=True)


def delete_credential() -> None:
    """Forget the credential but keep the OAuth client registration; it is a public PKCE client, not a secret."""
    stored_client = load_config().get(OAUTH_CLIENT_KEY)
    if stored_client is None:
        delete_config()
        return
    save_config({OAUTH_CLIENT_KEY: stored_client})


def resolve_api_key(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    from_env = os.environ.get(ENV_API_KEY)
    if from_env:
        return from_env
    from_file = load_config().get("api_key")
    if from_file:
        return str(from_file)
    raise AuthenticationError(NO_CREDENTIAL_MESSAGE)


def load_credential() -> Credential | None:
    config = load_config()
    if config.get("auth_method") == AUTH_METHOD_OAUTH:
        return OAuthCredential.from_config(config["oauth"])
    api_key = config.get("api_key")
    return ApiKeyCredential(api_key=str(api_key)) if api_key else None


def save_credential(credential: Credential) -> None:
    if isinstance(credential, OAuthCredential):
        config: dict[str, Any] = {"auth_method": AUTH_METHOD_OAUTH, "oauth": credential.to_config()}
    else:
        config = {"auth_method": AUTH_METHOD_API_KEY, "api_key": credential.api_key}
    stored_client = load_config().get(OAUTH_CLIENT_KEY)
    if stored_client is not None:
        config[OAUTH_CLIENT_KEY] = stored_client
    save_config(config)


def load_oauth_client() -> OAuthClientRegistration | None:
    stored = load_config().get(OAUTH_CLIENT_KEY)
    return OAuthClientRegistration.from_config(stored) if stored else None


def save_oauth_client(registration: OAuthClientRegistration) -> None:
    save_config({**load_config(), OAUTH_CLIENT_KEY: registration.to_config()})


def resolve_credential(*, api_key: str | None = None, auth: Credential | None = None) -> Credential:
    if auth is not None:
        return auth
    if api_key:
        return ApiKeyCredential(api_key=api_key)
    from_env = os.environ.get(ENV_API_KEY)
    if from_env:
        return ApiKeyCredential(api_key=from_env)
    credential = load_credential()
    if credential is not None:
        return credential
    raise AuthenticationError(NO_CREDENTIAL_MESSAGE)
