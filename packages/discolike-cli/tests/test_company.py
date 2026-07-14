from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest
from typer.testing import CliRunner

import discolike_cli.main as cli_main
from conftest import make_client
from discolike_cli.main import app

runner = CliRunner()


def _install_build_client(monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response]) -> None:
    monkeypatch.setattr(cli_main, "build_client", lambda **kwargs: make_client(handler))


@pytest.mark.parametrize(
    ("args", "expected_path"),
    [
        (["company", "data", "acme.com"], "/v1/bizdata"),
        (["company", "score", "acme.com"], "/v1/score"),
        (["company", "growth", "acme.com"], "/v1/growth"),
        (["company", "metrics", "acme.com"], "/v1/metrics"),
        (["company", "history", "acme.com"], "/v1/history"),
        (["company", "redirects", "acme.com"], "/v1/redirects"),
        (["company", "vendors", "acme.com"], "/v1/vendors"),
        (["company", "subsidiaries", "acme.com"], "/v1/subsidiaries"),
    ],
)
def test_company_subcommands_route_to_expected_path(
    monkeypatch: pytest.MonkeyPatch, args: list[str], expected_path: str
) -> None:
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json={"ok": True})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    request = captured["request"]
    assert request.url.path == expected_path
    assert request.url.params.get("domain") == "acme.com"
    assert json.loads(result.stdout) == {"ok": True}


def test_company_history_passes_max_records(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json={"ok": True})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["company", "history", "acme.com", "--max-records", "10"])
    assert result.exit_code == 0, result.output
    assert captured["request"].url.params.get("max_records") == "10"


@pytest.mark.parametrize("subcommand", ["redirects", "vendors", "subsidiaries"])
def test_company_match_option_forwarded(monkeypatch: pytest.MonkeyPatch, subcommand: str) -> None:
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json={"ok": True})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["company", subcommand, "acme.com", "--match", "loose"])
    assert result.exit_code == 0, result.output
    assert captured["request"].url.params.get("match") == "loose"


def test_company_public_links_hits_publiclink_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json={"ok": True})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["company", "public-links", "acme.com", "--source", "crunchbase"])
    assert result.exit_code == 0, result.output
    request = captured["request"]
    assert request.url.path == "/v1/publiclink"
    assert request.url.params.get("domain") == "acme.com"
    assert request.url.params.get("source") == "crunchbase"


def test_company_public_links_requires_source(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["company", "public-links", "acme.com"])
    assert result.exit_code == 2


def test_company_data_format_table_falls_back_to_json_for_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"name": "Acme", "domain": "acme.com"})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["company", "data", "acme.com", "--format", "table"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"name": "Acme", "domain": "acme.com"}


def test_extract_hits_extract_endpoint_with_url(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json={"text": "hello"})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["extract", "https://acme.com/about"])
    assert result.exit_code == 0, result.output
    request = captured["request"]
    assert request.url.path == "/v1/extract"
    assert request.url.params.get("url") == "https://acme.com/about"
    assert json.loads(result.stdout) == {"text": "hello"}
