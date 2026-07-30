from __future__ import annotations

import json
from collections.abc import Callable

import httpx
from typer.testing import CliRunner

from discolike_cli.main import app
from discolike_testkit import Handler

runner = CliRunner()


def _discover_ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=[{"domain": "acme.com"}])


def _count_ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"count": 42})


def _unauthorized(request: httpx.Request) -> httpx.Response:
    return httpx.Response(401, json={"detail": "invalid key"})


def test_discover_sends_options_and_param_escape_hatch(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, httpx.QueryParams] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = request.url.params
        return _discover_ok(request)

    install_build_client(handler)
    result = runner.invoke(
        app,
        ["discover", "--icp-prompt", "X", "--country", "DE", "--param", "min_similarity=200"],
    )
    assert result.exit_code == 0, result.output
    params = captured["params"]
    assert params.get("icp_prompt") == "X"
    assert params.get_list("country") == ["DE"]
    assert params.get("min_similarity") == "200"
    stdout = json.loads(result.stdout)
    assert stdout[0]["domain"] == "acme.com"


def test_discover_param_with_comma_value_becomes_list(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, httpx.QueryParams] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = request.url.params
        return _discover_ok(request)

    install_build_client(handler)
    result = runner.invoke(app, ["discover", "--param", "social=linkedin,github"])
    assert result.exit_code == 0, result.output
    assert captured["params"].get_list("social") == ["linkedin", "github"]


def test_discover_param_without_equals_exits_2(install_build_client: Callable[[Handler], None]) -> None:
    install_build_client(_discover_ok)
    result = runner.invoke(app, ["discover", "--param", "bogus"])
    assert result.exit_code == 2


def test_discover_param_removed_kwarg_exits_2(install_build_client: Callable[[Handler], None]) -> None:
    install_build_client(_discover_ok)
    result = runner.invoke(app, ["discover", "--param", "min_score=1"])
    assert result.exit_code == 2


def test_discover_explicit_option_wins_over_param_duplicate(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, httpx.QueryParams] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = request.url.params
        return _discover_ok(request)

    install_build_client(handler)
    result = runner.invoke(app, ["discover", "--country", "DE", "--param", "country=US"])
    assert result.exit_code == 0, result.output
    assert captured["params"].get_list("country") == ["DE"]


def test_discover_negate_option_forwarded(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, httpx.QueryParams] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = request.url.params
        return _discover_ok(request)

    install_build_client(handler)
    result = runner.invoke(app, ["discover", "--negate-country", "DE"])
    assert result.exit_code == 0, result.output
    assert captured["params"].get_list("negate_country") == ["DE"]


def test_discover_icp_text_option_removed(install_build_client: Callable[[Handler], None]) -> None:
    install_build_client(_discover_ok)
    result = runner.invoke(app, ["discover", "--icp-text", "X"])
    assert result.exit_code == 2


def test_count_sends_shared_filter_subset(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, httpx.QueryParams] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = request.url.params
        return _count_ok(request)

    install_build_client(handler)
    result = runner.invoke(app, ["count", "--category", "SAAS", "--param", "subdomain=shop"])
    assert result.exit_code == 0, result.output
    assert captured["params"].get_list("category") == ["SAAS"]
    assert captured["params"].get("subdomain") == "shop"
    assert json.loads(result.stdout) == {"count": 42}


def test_count_param_without_equals_exits_2(install_build_client: Callable[[Handler], None]) -> None:
    install_build_client(_count_ok)
    result = runner.invoke(app, ["count", "--param", "bogus"])
    assert result.exit_code == 2


def test_discover_unauthorized_exits_3(install_build_client: Callable[[Handler], None]) -> None:
    install_build_client(_unauthorized)
    result = runner.invoke(app, ["discover", "--icp-prompt", "X"])
    assert result.exit_code == 3
    payload = json.loads(result.stderr)
    assert payload["error"] == "AuthenticationError"
