from __future__ import annotations

import json
import stat
from collections.abc import Callable

import httpx
import pytest
from typer.testing import CliRunner

import discolike_cli.main as cli_main
from conftest import make_client
from discolike._config import config_path
from discolike._config import save_config
from discolike_cli.main import app

runner = CliRunner()


def _install_build_client(monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response]) -> None:
    monkeypatch.setattr(cli_main, "build_client", lambda **kwargs: make_client(handler))


def _usage_ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"requests_mtd": 1, "records_mtd": 2, "spend_mtd": 3.0})


def _usage_unauthorized(request: httpx.Request) -> httpx.Response:
    return httpx.Response(401, json={"detail": "invalid key"})


def test_login_with_api_key_option_verifies_and_saves(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_build_client(monkeypatch, _usage_ok)
    result = runner.invoke(app, ["auth", "login", "--api-key", "dk-1"])
    assert result.exit_code == 0, result.output
    assert json.loads(config_path().read_text())["api_key"] == "dk-1"
    mode = stat.S_IMODE(config_path().stat().st_mode)
    assert mode == 0o600
    payload = json.loads(result.stderr)
    assert payload["logged_in"] is True


def test_login_prompts_for_key_when_not_given(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_build_client(monkeypatch, _usage_ok)
    result = runner.invoke(app, ["auth", "login"], input="dk-2\n")
    assert result.exit_code == 0, result.output
    assert json.loads(config_path().read_text())["api_key"] == "dk-2"


def test_login_failed_verify_exits_3_and_writes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_build_client(monkeypatch, _usage_unauthorized)
    result = runner.invoke(app, ["auth", "login", "--api-key", "bad-key"])
    assert result.exit_code == 3
    assert not config_path().exists()
    payload = json.loads(result.stderr)
    assert payload["error"] == "AuthenticationError"


def test_status_masks_key_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_build_client(monkeypatch, _usage_ok)
    monkeypatch.setenv("DISCOLIKE_API_KEY", "dk-abcdefgh1234")
    result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["source"] == "env"
    assert payload["api_key"] == "…1234"
    assert payload["valid"] is True


def test_status_masks_key_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_build_client(monkeypatch, _usage_ok)
    save_config({"auth_method": "api_key", "api_key": "dk-zzzzzzzz5678"})
    result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["source"] == "config"
    assert payload["api_key"] == "…5678"


def test_status_no_key_exits_3_with_guidance(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_build_client(monkeypatch, _usage_ok)
    result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code == 3
    payload = json.loads(result.stderr)
    assert "DISCOLIKE_API_KEY" in payload["message"]
    assert "discolike auth login" in payload["message"]


def test_status_verify_failure_maps_through_handle_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_build_client(monkeypatch, _usage_unauthorized)
    monkeypatch.setenv("DISCOLIKE_API_KEY", "dk-badbadbad999")
    result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code == 3
    payload = json.loads(result.stderr)
    assert payload["error"] == "AuthenticationError"


def test_logout_removes_config_file(monkeypatch: pytest.MonkeyPatch) -> None:
    save_config({"auth_method": "api_key", "api_key": "dk-1"})
    assert config_path().exists()
    result = runner.invoke(app, ["auth", "logout"])
    assert result.exit_code == 0, result.output
    assert not config_path().exists()
    assert json.loads(result.stdout) == {"logged_out": True}


def test_cli_help_shows_auth_subcommand() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "auth" in result.output


def test_cli_version_flag() -> None:
    from discolike import __version__

    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output
