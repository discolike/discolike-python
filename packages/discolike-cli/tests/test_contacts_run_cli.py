from __future__ import annotations

import json
import pathlib
import time
from collections.abc import Callable
from typing import Any

import httpx2
import pytest
from typer.testing import CliRunner

from discolike_cli.main import app
from discolike_testkit import Handler

runner = CliRunner()

RUN_ID = "00000000-0000-0000-0000-0000000000bb"
RUN_PATH = f"/v1/contacts/run/{RUN_ID}"
TIMESTAMP = "2026-10-30T12:00:00Z"
STEPS = ("find_contacts", "find_missing", "review", "find_emails")


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "sleep", lambda seconds: None)


def run_payload(*, status: str = "waiting", step: int = 0, generation: int = 1) -> dict[str, Any]:
    return {
        "id": RUN_ID,
        "kind": "contacts",
        "status": status,
        "current_step": STEPS[step],
        "generation": generation,
        "steps": {STEPS[step]: {"status": "done"}},
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "expires_at": TIMESTAMP,
    }


def test_run_create_posts_params_file(install_build_client: Callable[[Handler], None], tmp_path: pathlib.Path) -> None:
    bodies: list[dict[str, Any]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(json.loads(request.content))
        return httpx2.Response(202, json=run_payload(status="running"))

    install_build_client(handler)
    params_file = tmp_path / "run.json"
    params_file.write_text(
        json.dumps({"companies": {"source": "prompt", "icp_text": "dental clinics"}, "people": {"titles": ["Owner"]}})
    )
    result = runner.invoke(
        app, ["contacts", "run", "create", "--params-file", str(params_file), "--email-cap-usd", "20"]
    )

    assert result.exit_code == 0, result.output
    assert bodies == [
        {
            "companies": {"source": "prompt", "icp_text": "dental clinics"},
            "people": {"titles": ["Owner"]},
            "email_cap_usd": "20.0",
        }
    ]
    assert json.loads(result.stdout)["status"] == "running"


def test_run_continue_fetches_generation_when_omitted(install_build_client: Callable[[Handler], None]) -> None:
    seen: list[tuple[str, str, Any]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content) if request.content else None
        seen.append((request.method, request.url.path, body))
        return httpx2.Response(200, json=run_payload(generation=4))

    install_build_client(handler)
    result = runner.invoke(
        app, ["contacts", "run", "continue", RUN_ID, "--not-fit-id", "r1", "--relevance", "balanced"]
    )

    assert result.exit_code == 0, result.output
    assert seen == [
        ("GET", RUN_PATH, None),
        ("POST", f"{RUN_PATH}/continue", {"generation": 4, "relevance": "balanced", "not_fit_ids": ["r1"]}),
    ]


def test_run_wait_follow_needs_cap_for_emails(install_build_client: Callable[[Handler], None]) -> None:
    state = {"step": 0}
    continues: list[dict[str, Any]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.method == "POST":
            continues.append(json.loads(request.content))
            state["step"] += 1
        step = state["step"]
        return httpx2.Response(
            200,
            json=run_payload(status="done" if step == len(STEPS) - 1 else "waiting", step=step, generation=step + 1),
        )

    install_build_client(handler)
    paused = runner.invoke(app, ["contacts", "run", "wait", RUN_ID, "--follow"])
    assert paused.exit_code == 0, paused.output
    assert json.loads(paused.stdout)["current_step"] == "review"

    finished = runner.invoke(app, ["contacts", "run", "wait", RUN_ID, "--follow", "--email-cap-usd", "15"])
    assert finished.exit_code == 0, finished.output
    assert json.loads(finished.stdout)["status"] == "done"
    assert continues == [{"generation": 1}, {"generation": 2}, {"generation": 3, "email_cap_usd": "15.0"}]


def test_run_cancel_and_get(install_build_client: Callable[[Handler], None]) -> None:
    seen: list[tuple[str, str, str]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append((request.method, request.url.path, request.url.query.decode()))
        return httpx2.Response(200, json=run_payload(status="cancelled"))

    install_build_client(handler)
    assert runner.invoke(app, ["contacts", "run", "cancel", RUN_ID]).exit_code == 0
    assert runner.invoke(app, ["contacts", "run", "get", RUN_ID, "--rows-limit", "10"]).exit_code == 0
    assert seen == [("POST", f"{RUN_PATH}/cancel", ""), ("GET", RUN_PATH, "rows_limit=10")]


def test_run_list_sends_before(install_build_client: Callable[[Handler], None]) -> None:
    queries: list[httpx2.QueryParams] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        queries.append(request.url.params)
        return httpx2.Response(200, json=[run_payload()])

    install_build_client(handler)
    result = runner.invoke(app, ["contacts", "run", "list", "--before", "2026-10-30T00:00:00+00:00", "--limit", "5"])
    assert result.exit_code == 0, result.output
    assert queries[0]["before"] == "2026-10-30T00:00:00Z"
    assert queries[0]["limit"] == "5"


def test_run_title_preview(install_build_client: Callable[[Handler], None]) -> None:
    bodies: list[dict[str, Any]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(json.loads(request.content))
        return httpx2.Response(200, json={"titles": [{"title": "Owner", "role": 1.0, "count": 3}]})

    install_build_client(handler)
    result = runner.invoke(app, ["contacts", "run", "title-preview", "--title", "Owner", "--format", "json"])
    assert result.exit_code == 0, result.output
    assert bodies == [{"titles": ["Owner"], "match": "similar"}]
    assert json.loads(result.stdout) == [{"title": "Owner", "role": 1.0, "count": 3}]


@pytest.mark.parametrize("command", ["search", "count"])
def test_old_contacts_commands_print_deprecation(install_build_client: Callable[[Handler], None], command: str) -> None:
    install_build_client(lambda request: httpx2.Response(200, json=[] if command == "search" else {"count": 0}))
    result = runner.invoke(app, ["contacts", command, "--name", "Jane"])
    assert result.exit_code == 0, result.output
    assert f"`discolike contacts {command}` is deprecated" in result.stderr
    assert "use `discolike contacts run`" in result.stderr


def test_contacts_discover_prints_no_deprecation(install_build_client: Callable[[Handler], None]) -> None:
    install_build_client(lambda request: httpx2.Response(200, json={"results": {}}))
    result = runner.invoke(app, ["contacts", "discover", "--domain", "acme.com"])
    assert result.exit_code == 0, result.output
    assert "deprecated" not in result.stderr


def test_email_find_sends_suggested_email(install_build_client: Callable[[Handler], None]) -> None:
    bodies: list[dict[str, Any]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(json.loads(request.content))
        return httpx2.Response(202, json={"job_id": "j-1", "status": "queued"})

    install_build_client(handler)
    result = runner.invoke(app, ["email", "find", "Grace", "Hopper", "navy.mil", "--suggested-email", "grace@navy.mil"])
    assert result.exit_code == 0, result.output
    assert bodies == [
        {"first_name": "Grace", "last_name": "Hopper", "domain": "navy.mil", "suggested_email": "grace@navy.mil"}
    ]
