from __future__ import annotations

import json
from collections.abc import Callable

import httpx2
from typer.testing import CliRunner

from discolike_cli.main import app
from discolike_testkit import Handler

runner = CliRunner()


def _discover_ok(request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(200, json=[{"domain": "acme.com"}])


def _count_ok(request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(200, json={"count": 42})


def _unauthorized(request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(401, json={"detail": "invalid key"})


def test_discover_sends_options_and_param_escape_hatch(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, httpx2.QueryParams] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["params"] = request.url.params
        return _discover_ok(request)

    install_build_client(handler)
    result = runner.invoke(
        app,
        ["discover", "--icp-prompt", "X", "--country", "DE", "--param", "min_similarity=50"],
    )
    assert result.exit_code == 0, result.output
    params = captured["params"]
    assert params.get("icp_prompt") == "X"
    assert params.get_list("country") == ["DE"]
    assert params.get("min_similarity") == "50"
    stdout = json.loads(result.stdout)
    assert stdout[0]["domain"] == "acme.com"


def test_discover_param_with_comma_value_becomes_list(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, httpx2.QueryParams] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["params"] = request.url.params
        return _discover_ok(request)

    install_build_client(handler)
    result = runner.invoke(app, ["discover", "--param", "social=linkedin,youtube"])
    assert result.exit_code == 0, result.output
    assert captured["params"].get_list("social") == ["linkedin", "youtube"]


def test_discover_param_without_equals_exits_2(install_build_client: Callable[[Handler], None]) -> None:
    install_build_client(_discover_ok)
    result = runner.invoke(app, ["discover", "--param", "bogus"])
    assert result.exit_code == 2


def test_discover_param_unknown_key_passes_through(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, httpx2.QueryParams] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["params"] = request.url.params
        return _discover_ok(request)

    install_build_client(handler)
    result = runner.invoke(app, ["discover", "--param", "min_score=1"])
    assert result.exit_code == 0, result.output
    assert captured["params"].get("min_score") == "1"


def test_discover_param_out_of_range_exits_2(install_build_client: Callable[[Handler], None]) -> None:
    install_build_client(_discover_ok)
    result = runner.invoke(app, ["discover", "--param", "min_similarity=200"])
    assert result.exit_code == 2
    payload = json.loads(result.stderr)
    assert payload["error"] == "ValidationError"
    assert "min_similarity" in payload["message"]


def test_discover_explicit_option_wins_over_param_duplicate(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, httpx2.QueryParams] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["params"] = request.url.params
        return _discover_ok(request)

    install_build_client(handler)
    result = runner.invoke(app, ["discover", "--country", "DE", "--param", "country=US"])
    assert result.exit_code == 0, result.output
    assert captured["params"].get_list("country") == ["DE"]


def test_discover_negate_option_forwarded(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, httpx2.QueryParams] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
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


def test_discover_forwards_every_new_flag(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, httpx2.QueryParams] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["params"] = request.url.params
        return _discover_ok(request)

    install_build_client(handler)
    result = runner.invoke(
        app,
        [
            "discover",
            "--subdomain",
            "shop",
            "--negate-subdomain",
            "blog",
            "--language",
            "en",
            "--negate-language",
            "de",
            "--social",
            "linkedin",
            "--negate-social",
            "tiktok",
            "--start-date",
            "2020-01-01",
            "--min-similarity",
            "40",
            "--variance",
            "MEDIUM",
            "--consensus",
            "3",
            "--redirect",
            "--no-exclude-leadgen",
            "--retrieval",
            "--enhanced",
            "--include-search-domains",
            "--auto-icp-text",
            "--auto-phrase-match",
            "--inclusion-query-id",
            "q1",
        ],
    )
    assert result.exit_code == 0, result.output
    params = captured["params"]
    assert params.get_list("subdomain") == ["shop"]
    assert params.get_list("negate_subdomain") == ["blog"]
    assert params.get_list("language") == ["en"]
    assert params.get_list("negate_language") == ["de"]
    assert params.get_list("social") == ["linkedin"]
    assert params.get_list("negate_social") == ["tiktok"]
    assert params.get("start_date") == "2020-01-01"
    assert params.get("min_similarity") == "40"
    assert params.get("variance") == "MEDIUM"
    assert params.get("consensus") == "3"
    assert params.get("redirect") == "true"
    assert params.get("exclude_leadgen") == "false"
    assert params.get("retrieval") == "true"
    assert params.get("enhanced") == "true"
    assert params.get("include_search_domains") == "true"
    assert params.get("auto_icp_text") == "true"
    assert params.get("auto_phrase_match") == "true"
    assert params.get_list("inclusion_query_id") == ["q1"]


def test_discover_rejects_invalid_variance(install_build_client: Callable[[Handler], None]) -> None:
    install_build_client(_discover_ok)
    result = runner.invoke(app, ["discover", "--variance", "BOGUS"])
    assert result.exit_code == 2


def test_count_forwards_every_new_flag(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, httpx2.QueryParams] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["params"] = request.url.params
        return _count_ok(request)

    install_build_client(handler)
    result = runner.invoke(
        app,
        [
            "count",
            "--subdomain",
            "shop",
            "--negate-subdomain",
            "blog",
            "--language",
            "en",
            "--negate-language",
            "de",
            "--social",
            "linkedin",
            "--negate-social",
            "tiktok",
            "--start-date",
            "2020-01-01,2021-01-01",
            "--no-redirect",
            "--exclude-leadgen",
        ],
    )
    assert result.exit_code == 0, result.output
    params = captured["params"]
    assert params.get_list("subdomain") == ["shop"]
    assert params.get_list("negate_subdomain") == ["blog"]
    assert params.get_list("language") == ["en"]
    assert params.get_list("negate_language") == ["de"]
    assert params.get_list("social") == ["linkedin"]
    assert params.get_list("negate_social") == ["tiktok"]
    assert params.get("start_date") == "2020-01-01,2021-01-01"
    assert params.get("redirect") == "false"
    assert params.get("exclude_leadgen") == "true"


def test_count_sends_shared_filter_subset(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, httpx2.QueryParams] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
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
