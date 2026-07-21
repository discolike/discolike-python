from __future__ import annotations

import json
from collections.abc import Callable

import httpx
from typer.testing import CliRunner

from discolike_cli.main import app
from discolike_testkit import Handler

runner = CliRunner()


def test_queries_list_sends_params(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json={"results": [{"query_id": "q1"}]})

    install_build_client(handler)
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


def test_queries_create_exclusion_list_posts_json(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"query_id": "q2", "query_name": "My List"})

    install_build_client(handler)
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


def test_queries_update_patches_body(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["method"] = request.method
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"query_id": "q3", "query_name": "Renamed"})

    install_build_client(handler)
    result = runner.invoke(app, ["queries", "update", "q3", "--name", "Renamed", "--tag", "hot"])
    assert result.exit_code == 0, result.output
    assert captured["path"] == "/v1/queries/q3"
    assert captured["method"] == "PATCH"
    assert captured["body"] == {"query_name": "Renamed", "tags": ["hot"]}


def test_queries_delete_hits_delete_endpoint(install_build_client: Callable[[Handler], None]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/queries/q4"
        assert request.method == "DELETE"
        return httpx.Response(200, json={"message": "ok"})

    install_build_client(handler)
    result = runner.invoke(app, ["queries", "delete", "q4"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"deleted": "q4"}


def test_queries_save_results_json_input(monkeypatch, tmp_path):
    captured = {}

    def handler(request):
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"query_id": "q6", "row_count": 2})

    _install_build_client(monkeypatch, handler)
    f = tmp_path / "rows.json"
    f.write_text(json.dumps([{"domain": "a.com"}, {"domain": "b.com"}]))
    result = runner.invoke(
        app,
        ["queries", "save-results", "--input", str(f), "--name", "R", "--action", "discover"],
    )
    assert result.exit_code == 0, result.output
    assert captured["path"] == "/v1/queries/save-results"
    assert captured["body"]["data"] == [{"domain": "a.com"}, {"domain": "b.com"}]
    assert captured["body"]["query_name"] == "R"
    assert captured["body"]["action"] == "discover"


def test_queries_save_results_csv_input(monkeypatch, tmp_path):
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"query_id": "q7"})

    _install_build_client(monkeypatch, handler)
    f = tmp_path / "rows.csv"
    f.write_text("domain,score\na.com,1\nb.com,2\n")
    result = runner.invoke(
        app,
        ["queries", "save-results", "--input", str(f), "--name", "R", "--action", "discover"],
    )
    assert result.exit_code == 0, result.output
    assert captured["body"]["data"] == [{"domain": "a.com", "score": "1"}, {"domain": "b.com", "score": "2"}]
    assert captured["body"]["query_name"] == "R"
    assert captured["body"]["action"] == "discover"


def test_queries_save_results_missing_input_file_is_clean_error(monkeypatch, tmp_path):
    def handler(request):
        raise AssertionError("handler should not be reached for a missing --input file")

    _install_build_client(monkeypatch, handler)
    missing = tmp_path / "does-not-exist.json"
    result = runner.invoke(
        app,
        ["queries", "save-results", "--input", str(missing), "--name", "R", "--action", "discover"],
    )
    assert result.exit_code == 2, result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert "Traceback" not in result.output
    assert missing.name in result.output.replace("\n", "")
