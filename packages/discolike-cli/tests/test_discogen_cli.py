from __future__ import annotations

import json
from collections.abc import Callable

import httpx
from typer.testing import CliRunner

from discolike_cli.main import app
from discolike_testkit import Handler

runner = CliRunner()


def test_discogen_run_posts_json_and_prints_task_hint(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"task_id": "dg-1"})

    install_build_client(handler)
    result = runner.invoke(
        app,
        [
            "discogen",
            "run",
            "--query",
            "Recent funding rounds",
            "--domain",
            "acme.com",
            "--domain",
            "beta.com",
            "--web-search",
        ],
    )
    assert result.exit_code == 0, result.output
    assert captured["path"] == "/v1/discogen/process"
    assert captured["body"] == {
        "query": "Recent funding rounds",
        "domains": ["acme.com", "beta.com"],
        "web_search": True,
    }
    payload = json.loads(result.stdout)
    assert payload["task_id"] == "dg-1"
    assert payload["task_family"] == "discogen"


def test_discogen_run_sends_include_x_search_when_passed(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"task_id": "dg-1b"})

    install_build_client(handler)
    result = runner.invoke(
        app,
        ["discogen", "run", "--query", "q", "--domain", "acme.com", "--include-x-search"],
    )
    assert result.exit_code == 0, result.output
    assert captured["body"] == {
        "query": "q",
        "domains": ["acme.com"],
        "include_x_search": True,
    }


def test_discogen_run_personas_posts_persona_ids(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"task_id": "dg-2"})

    install_build_client(handler)
    result = runner.invoke(
        app,
        ["discogen", "run-personas", "--query", "Career history", "--persona-id", "1", "--persona-id", "2"],
    )
    assert result.exit_code == 0, result.output
    assert captured["path"] == "/v1/discogen/process-personas"
    assert captured["body"] == {
        "query": "Career history",
        "persona_ids": [1, 2],
    }


def test_discogen_run_personas_sends_include_x_search_when_passed(
    install_build_client: Callable[[Handler], None],
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"task_id": "dg-2b"})

    install_build_client(handler)
    result = runner.invoke(
        app,
        ["discogen", "run-personas", "--query", "q", "--persona-id", "1", "--include-x-search"],
    )
    assert result.exit_code == 0, result.output
    assert captured["body"] == {
        "query": "q",
        "persona_ids": [1],
        "include_x_search": True,
    }


def test_discogen_run_with_wait_polls_to_completion(install_build_client: Callable[[Handler], None]) -> None:
    statuses = iter(
        [
            httpx.Response(200, json={"status": "processing", "progress": 50}),
            httpx.Response(200, json={"status": "completed", "progress": 100, "results": [{"summary": "ok"}]}),
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/discogen/process":
            return httpx.Response(200, json={"task_id": "dg-3"})
        assert request.url.path == "/v1/discogen/status/dg-3"
        return next(statuses)

    install_build_client(handler)
    result = runner.invoke(
        app,
        ["discogen", "run", "--query", "q", "--domain", "acme.com", "--wait", "--timeout", "5"],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == [{"summary": "ok"}]
    assert "progress: 50%" in result.stderr


def test_discogen_models_hits_models_endpoint(install_build_client: Callable[[Handler], None]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/discogen/models"
        return httpx.Response(200, json={"models": ["default"]})

    install_build_client(handler)
    result = runner.invoke(app, ["discogen", "models"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"models": ["default"]}


def test_discogen_status_default_family_discogen(install_build_client: Callable[[Handler], None]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/discogen/status/dg-4"
        return httpx.Response(200, json={"status": "completed", "progress": 100})

    install_build_client(handler)
    result = runner.invoke(app, ["discogen", "status", "dg-4"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["status"] == "completed"


def test_discogen_status_with_family_segment(install_build_client: Callable[[Handler], None]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/segment/status/seg-1"
        return httpx.Response(200, json={"status": "processing", "progress": 10})

    install_build_client(handler)
    result = runner.invoke(app, ["discogen", "status", "seg-1", "--family", "segment"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["status"] == "processing"


def test_discogen_cancel_hits_cancel_endpoint(install_build_client: Callable[[Handler], None]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/discogen/cancel/dg-5"
        assert request.method == "DELETE"
        return httpx.Response(200, json={"ok": True})

    install_build_client(handler)
    result = runner.invoke(app, ["discogen", "cancel", "dg-5"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"cancelled": "dg-5"}


def test_discogen_cancel_with_family_bulkmatch(install_build_client: Callable[[Handler], None]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/bulkmatch/cancel/bm-1"
        return httpx.Response(200, json={"ok": True})

    install_build_client(handler)
    result = runner.invoke(app, ["discogen", "cancel", "bm-1", "--family", "bulkmatch"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"cancelled": "bm-1"}


def test_discogen_status_invalid_family_exits_2(install_build_client: Callable[[Handler], None]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    install_build_client(handler)
    result = runner.invoke(app, ["discogen", "status", "dg-6", "--family", "bogus"])
    assert result.exit_code == 2
