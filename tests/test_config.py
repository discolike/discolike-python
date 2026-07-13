import stat

import pytest

from discolike import AuthenticationError
from discolike._config import config_path, load_config, resolve_api_key, save_config


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("DISCOLIKE_API_KEY", raising=False)
    return tmp_path


def test_save_and_load_roundtrip(isolated_config) -> None:
    save_config({"auth_method": "api_key", "api_key": "dk-123"})
    assert load_config()["api_key"] == "dk-123"
    mode = stat.S_IMODE(config_path().stat().st_mode)
    assert mode == 0o600


def test_save_tightens_preexisting_loose_mode(isolated_config) -> None:
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text("{}")
    config_path().chmod(0o644)
    save_config({"auth_method": "api_key", "api_key": "dk-456"})
    assert load_config()["api_key"] == "dk-456"
    mode = stat.S_IMODE(config_path().stat().st_mode)
    assert mode == 0o600


def test_load_missing_returns_empty(isolated_config) -> None:
    assert load_config() == {}


def test_resolve_precedence_explicit_wins(isolated_config, monkeypatch) -> None:
    save_config({"auth_method": "api_key", "api_key": "from-file"})
    monkeypatch.setenv("DISCOLIKE_API_KEY", "from-env")
    assert resolve_api_key("explicit") == "explicit"
    assert resolve_api_key(None) == "from-env"
    monkeypatch.delenv("DISCOLIKE_API_KEY")
    assert resolve_api_key(None) == "from-file"


def test_resolve_nothing_raises_with_guidance(isolated_config) -> None:
    with pytest.raises(AuthenticationError) as exc_info:
        resolve_api_key(None)
    assert "DISCOLIKE_API_KEY" in str(exc_info.value)
    assert "discolike auth login" in str(exc_info.value)


def test_corrupt_config_returns_empty(isolated_config) -> None:
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text("{not json")
    assert load_config() == {}


def test_binary_garbage_config_returns_empty(isolated_config) -> None:
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_bytes(b"\xff\xfe\x00garbage")
    assert load_config() == {}
