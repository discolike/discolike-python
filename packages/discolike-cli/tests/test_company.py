from __future__ import annotations

import json
from collections.abc import Callable

import httpx2
import pytest
from typer.testing import CliRunner

from discolike_cli.main import app
from discolike_testkit import Handler

runner = CliRunner()


@pytest.mark.parametrize(
    ("args", "expected_path"),
    [
        (["company", "data", "acme.com"], "/v1/bizdata"),
        (["company", "score", "acme.com"], "/v1/score"),
        (["company", "growth", "acme.com"], "/v1/growth"),
    ],
)
def test_company_subcommands_route_to_expected_path(
    args: list[str], expected_path: str, install_build_client: Callable[[Handler], None]
) -> None:
    captured: dict[str, httpx2.Request] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["request"] = request
        return httpx2.Response(200, json={"domain": "acme.com", "ok": True})

    install_build_client(handler)
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    request = captured["request"]
    assert request.url.path == expected_path
    assert request.url.params.get("domain") == "acme.com"
    assert json.loads(result.stdout)["ok"] is True


@pytest.mark.parametrize(
    ("args", "expected_path"),
    [
        (["company", "redirects", "acme.com"], "/v1/redirects"),
        (["company", "vendors", "acme.com"], "/v1/vendors"),
        (["company", "subsidiaries", "acme.com"], "/v1/subsidiaries"),
    ],
)
def test_company_list_subcommands_route_to_expected_path(
    args: list[str], expected_path: str, install_build_client: Callable[[Handler], None]
) -> None:
    captured: dict[str, httpx2.Request] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["request"] = request
        return httpx2.Response(200, json=[{"linked_domain": "acme.io", "ok": True}])

    install_build_client(handler)
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    request = captured["request"]
    assert request.url.path == expected_path
    assert request.url.params.get("domain") == "acme.com"
    rows = json.loads(result.stdout)
    assert rows[0]["linked_domain"] == "acme.io"


@pytest.mark.parametrize("subcommand", ["redirects", "vendors", "subsidiaries"])
def test_company_match_option_forwarded(subcommand: str, install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, httpx2.Request] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["request"] = request
        return httpx2.Response(200, json=[{"linked_domain": "acme.io"}])

    install_build_client(handler)
    result = runner.invoke(app, ["company", subcommand, "acme.com", "--match", "loose"])
    assert result.exit_code == 0, result.output
    assert captured["request"].url.params.get("match") == "loose"


def test_company_public_links_hits_publiclink_endpoint(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, httpx2.Request] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["request"] = request
        return httpx2.Response(200, json=[{"linked_domain": "acme.io"}])

    install_build_client(handler)
    result = runner.invoke(app, ["company", "public-links", "acme.com", "--source", "crunchbase"])
    assert result.exit_code == 0, result.output
    request = captured["request"]
    assert request.url.path == "/v1/publiclink"
    assert request.url.params.get("domain") == "acme.com"
    assert request.url.params.get("source") == "crunchbase"


def test_company_public_links_requires_source(install_build_client: Callable[[Handler], None]) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"ok": True})

    install_build_client(handler)
    result = runner.invoke(app, ["company", "public-links", "acme.com"])
    assert result.exit_code == 2


def test_company_data_format_table_falls_back_to_json_for_dict(install_build_client: Callable[[Handler], None]) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"name": "Acme", "domain": "acme.com"})

    install_build_client(handler)
    result = runner.invoke(app, ["company", "data", "acme.com", "--format", "table"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    assert payload["name"] == "Acme"
    assert payload["domain"] == "acme.com"


def test_extract_hits_extract_endpoint_with_url(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, httpx2.Request] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["request"] = request
        return httpx2.Response(200, json={"text": "hello", "language": "en"})

    install_build_client(handler)
    result = runner.invoke(app, ["extract", "https://acme.com/about"])
    assert result.exit_code == 0, result.output
    request = captured["request"]
    assert request.url.path == "/v1/extract"
    assert request.url.params.get("url") == "https://acme.com/about"
    assert json.loads(result.stdout) == {"text": "hello", "language": "en"}
