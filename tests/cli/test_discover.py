from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest
from typer.testing import CliRunner

import discolike.cli.main as cli_main
from conftest import make_client
from discolike.cli.main import app

runner = CliRunner()


def _install_build_client(monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response]) -> None:
    monkeypatch.setattr(cli_main, "build_client", lambda **kwargs: make_client(handler))


def _discover_ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=[{"domain": "acme.com"}])


def _count_ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"count": 42})


def _unauthorized(request: httpx.Request) -> httpx.Response:
    return httpx.Response(401, json={"detail": "invalid key"})


def test_discover_sends_options_and_param_escape_hatch(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, httpx.QueryParams] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = request.url.params
        return _discover_ok(request)

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(
        app,
        ["discover", "--icp-prompt", "X", "--country", "DE", "--param", "min_score=200"],
    )
    assert result.exit_code == 0, result.output
    params = captured["params"]
    assert params.get("icp_prompt") == "X"
    assert params.get_list("country") == ["DE"]
    assert params.get("min_score") == "200"
    stdout = json.loads(result.stdout)
    assert stdout[0]["domain"] == "acme.com"


def test_discover_param_with_comma_value_becomes_list(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, httpx.QueryParams] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = request.url.params
        return _discover_ok(request)

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["discover", "--param", "vendor=stripe,twilio"])
    assert result.exit_code == 0, result.output
    assert captured["params"].get_list("vendor") == ["stripe", "twilio"]


def test_discover_param_without_equals_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_build_client(monkeypatch, _discover_ok)
    result = runner.invoke(app, ["discover", "--param", "bogus"])
    assert result.exit_code == 2


def test_discover_explicit_option_wins_over_param_duplicate(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, httpx.QueryParams] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = request.url.params
        return _discover_ok(request)

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["discover", "--country", "DE", "--param", "country=US"])
    assert result.exit_code == 0, result.output
    assert captured["params"].get_list("country") == ["DE"]


def test_count_sends_shared_filter_subset(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, httpx.QueryParams] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = request.url.params
        return _count_ok(request)

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["count", "--category", "SAAS", "--param", "min_score=5"])
    assert result.exit_code == 0, result.output
    assert captured["params"].get_list("category") == ["SAAS"]
    assert captured["params"].get("min_score") == "5"
    assert json.loads(result.stdout) == {"count": 42}


def test_count_param_without_equals_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_build_client(monkeypatch, _count_ok)
    result = runner.invoke(app, ["count", "--param", "bogus"])
    assert result.exit_code == 2


def test_discover_unauthorized_exits_3(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_build_client(monkeypatch, _unauthorized)
    result = runner.invoke(app, ["discover", "--icp-prompt", "X"])
    assert result.exit_code == 3
    payload = json.loads(result.stderr)
    assert payload["error"] == "AuthenticationError"
