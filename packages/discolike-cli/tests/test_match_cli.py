from __future__ import annotations

import json
from collections.abc import Callable

import httpx2
import pytest
from typer.testing import CliRunner

from discolike_cli.main import app
from discolike_testkit import Handler

runner = CliRunner()


def test_match_single_name_hits_match_endpoint(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, httpx2.Request] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["request"] = request
        return httpx2.Response(
            200,
            json={"query": {"name": "Acme"}, "matches": [{"domain": "acme.com", "match_confidence": 98.0}]},
        )

    install_build_client(handler)
    result = runner.invoke(app, ["match", "Acme"])
    assert result.exit_code == 0, result.output
    request = captured["request"]
    assert request.url.path == "/v1/match"
    assert request.url.params.get("name") == "Acme"
    payload = json.loads(result.stdout)
    assert payload["query"]["name"] == "Acme"
    assert payload["matches"][0]["domain"] == "acme.com"


def test_match_bulk_file_with_wait_polls_to_completion(
    tmp_path, install_build_client: Callable[[Handler], None]
) -> None:
    names_file = tmp_path / "names.csv"
    names_file.write_text("company\nAcme\n")
    statuses = iter(
        [
            httpx2.Response(200, json={"status": "processing", "progress": 40}),
            httpx2.Response(200, json={"status": "completed", "progress": 100, "results": [{"domain": "acme.com"}]}),
        ]
    )

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/v1/bulkmatch":
            return httpx2.Response(200, json={"task_id": "bm-1"})
        assert request.url.path == "/v1/bulkmatch/status/bm-1"
        return next(statuses)

    install_build_client(handler)
    result = runner.invoke(
        app,
        ["match", "--file", str(names_file), "--name-column", "company", "--wait", "--timeout", "5"],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == [{"domain": "acme.com"}]
    assert "progress: 40%" in result.stderr


def test_match_bulk_file_with_wait_format_table_renders_table(
    tmp_path, install_build_client: Callable[[Handler], None]
) -> None:
    names_file = tmp_path / "names.csv"
    names_file.write_text("company\nAcme\n")

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/v1/bulkmatch":
            return httpx2.Response(200, json={"task_id": "bm-5"})
        assert request.url.path == "/v1/bulkmatch/status/bm-5"
        return httpx2.Response(200, json={"status": "completed", "progress": 100, "results": [{"domain": "acme.com"}]})

    install_build_client(handler)
    result = runner.invoke(
        app,
        [
            "match",
            "--file",
            str(names_file),
            "--name-column",
            "company",
            "--wait",
            "--timeout",
            "5",
            "--format",
            "table",
        ],
    )
    assert result.exit_code == 0, result.output
    with pytest.raises(json.JSONDecodeError):
        json.loads(result.stdout)
    assert "domain" in result.stdout
    assert "acme.com" in result.stdout


def test_match_bulk_file_without_wait_prints_task_hint(
    tmp_path, install_build_client: Callable[[Handler], None]
) -> None:
    names_file = tmp_path / "names.csv"
    names_file.write_text("name\nAcme\n")

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/v1/bulkmatch"
        return httpx2.Response(200, json={"task_id": "bm-2"})

    install_build_client(handler)
    result = runner.invoke(app, ["match", "--file", str(names_file)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["task_id"] == "bm-2"
    assert payload["task_family"] == "bulkmatch"


def test_match_both_name_and_file_exits_2(tmp_path, install_build_client: Callable[[Handler], None]) -> None:
    names_file = tmp_path / "names.csv"
    names_file.write_text("name\nAcme\n")

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={})

    install_build_client(handler)
    result = runner.invoke(app, ["match", "Acme", "--file", str(names_file)])
    assert result.exit_code == 2


def test_match_neither_name_nor_file_exits_2(install_build_client: Callable[[Handler], None]) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={})

    install_build_client(handler)
    result = runner.invoke(app, ["match"])
    assert result.exit_code == 2


def test_match_passes_optional_filters(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, httpx2.Request] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["request"] = request
        return httpx2.Response(200, json={"domain": "acme.com"})

    install_build_client(handler)
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


def test_match_local_mode_omitted_when_not_passed(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, httpx2.Request] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["request"] = request
        return httpx2.Response(200, json={"domain": "acme.com"})

    install_build_client(handler)
    result = runner.invoke(app, ["match", "Acme"])
    assert result.exit_code == 0, result.output
    assert "local_mode" not in captured["request"].url.params


def test_match_bulk_local_mode_omitted_when_not_passed(
    tmp_path, install_build_client: Callable[[Handler], None]
) -> None:
    names_file = tmp_path / "names.csv"
    names_file.write_text("name\nAcme\n")
    captured: dict[str, httpx2.Request] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["request"] = request
        return httpx2.Response(200, json={"task_id": "bm-3"})

    install_build_client(handler)
    result = runner.invoke(app, ["match", "--file", str(names_file)])
    assert result.exit_code == 0, result.output
    assert "local_mode" not in captured["request"].url.params


def test_match_bulk_local_mode_sent_when_passed(tmp_path, install_build_client: Callable[[Handler], None]) -> None:
    names_file = tmp_path / "names.csv"
    names_file.write_text("name\nAcme\n")
    captured: dict[str, httpx2.Request] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["request"] = request
        return httpx2.Response(200, json={"task_id": "bm-4"})

    install_build_client(handler)
    result = runner.invoke(app, ["match", "--file", str(names_file), "--local-mode"])
    assert result.exit_code == 0, result.output
    assert captured["request"].url.params.get("local_mode") == "true"
