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


def test_queries_list_sends_params(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json={"results": [{"query_id": "q1"}]})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(
        app,
        ["queries", "list", "--max-records", "10", "--offset", "5", "--action", "discover", "--tag", "a", "--tag", "b"],
    )
    assert result.exit_code == 0, result.output
    request = captured["request"]
    assert request.url.path == "/v1/queries/saved"
    assert request.url.params.get("max_records") == "10"
    assert request.url.params.get("offset") == "5"
    assert request.url.params.get("action") == "discover"
    assert request.url.params.get_list("tags") == ["a", "b"]


def test_queries_create_exclusion_list_posts_json(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"query_id": "q2", "query_name": "My List"})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(
        app,
        [
            "queries",
            "create-exclusion-list",
            "--name",
            "My List",
            "--domain",
            "acme.com",
            "--persona-id",
            "1",
            "--tag",
            "cold",
        ],
    )
    assert result.exit_code == 0, result.output
    assert captured["path"] == "/v1/queries/exclusion-list"
    assert captured["body"] == {
        "query_name": "My List",
        "domains": ["acme.com"],
        "persona_ids": [1],
        "tags": ["cold"],
    }


def test_queries_update_patches_body(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["method"] = request.method
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"query_id": "q3", "query_name": "Renamed"})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["queries", "update", "q3", "--name", "Renamed", "--tag", "hot"])
    assert result.exit_code == 0, result.output
    assert captured["path"] == "/v1/queries/q3"
    assert captured["method"] == "PATCH"
    assert captured["body"] == {"query_name": "Renamed", "tags": ["hot"]}


def test_queries_delete_hits_delete_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/queries/q4"
        assert request.method == "DELETE"
        return httpx.Response(200, json={"message": "ok"})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["queries", "delete", "q4"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"deleted": "q4"}
