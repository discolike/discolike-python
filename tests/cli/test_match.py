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


def test_match_single_name_hits_match_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json={"domain": "acme.com"})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["match", "Acme"])
    assert result.exit_code == 0, result.output
    request = captured["request"]
    assert request.url.path == "/v1/match"
    assert request.url.params.get("name") == "Acme"
    assert json.loads(result.stdout) == {"domain": "acme.com"}


def test_match_bulk_file_with_wait_polls_to_completion(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    names_file = tmp_path / "names.csv"
    names_file.write_text("company\nAcme\n")
    statuses = iter(
        [
            httpx.Response(200, json={"status": "processing", "progress": 40}),
            httpx.Response(200, json={"status": "completed", "progress": 100, "results": [{"domain": "acme.com"}]}),
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/bulkmatch":
            return httpx.Response(200, json={"task_id": "bm-1"})
        assert request.url.path == "/v1/bulkmatch/status/bm-1"
        return next(statuses)

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(
        app,
        ["match", "--file", str(names_file), "--name-column", "company", "--wait", "--timeout", "5"],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == [{"domain": "acme.com"}]
    assert "progress: 40%" in result.stderr


def test_match_bulk_file_without_wait_prints_task_hint(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    names_file = tmp_path / "names.csv"
    names_file.write_text("name\nAcme\n")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/bulkmatch"
        return httpx.Response(200, json={"task_id": "bm-2"})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["match", "--file", str(names_file)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["task_id"] == "bm-2"
    assert payload["task_family"] == "bulkmatch"


def test_match_both_name_and_file_exits_2(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    names_file = tmp_path / "names.csv"
    names_file.write_text("name\nAcme\n")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["match", "Acme", "--file", str(names_file)])
    assert result.exit_code == 2


def test_match_neither_name_nor_file_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["match"])
    assert result.exit_code == 2


def test_match_passes_optional_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json={"domain": "acme.com"})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(
        app,
        [
            "match",
            "Acme",
            "--phone",
            "555-1234",
            "--city",
            "Austin",
            "--state",
            "TX",
            "--country",
            "US",
            "--zip-code",
            "78701",
            "--strict",
            "--local-mode",
        ],
    )
    assert result.exit_code == 0, result.output
    params = captured["request"].url.params
    assert params.get("phone") == "555-1234"
    assert params.get("city") == "Austin"
    assert params.get("state") == "TX"
    assert params.get("country") == "US"
    assert params.get("zip_code") == "78701"
    assert params.get("strict") == "true"
    assert params.get("local_mode") == "true"
