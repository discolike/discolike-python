from __future__ import annotations

import json
from collections.abc import Callable

import httpx2
from typer.testing import CliRunner

from discolike_cli.main import app
from discolike_testkit import Handler

runner = CliRunner()
RUN_ID = "00000000-0000-0000-0000-000000000001"


def test_start_forwards_key_and_brief(install_build_client: Callable[[Handler], None]) -> None:
    seen = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(202, json={"run_id": RUN_ID, "status": "queued", "max_actions": 24})

    install_build_client(handler)
    result = runner.invoke(
        app,
        [
            "prospecting",
            "start",
            "--brief",
            "US logistics companies and operations directors",
            "--idempotency-key",
            "pilot-key",
            "--exclude-domain",
            "excluded.com",
            "--target-companies",
            "10",
        ],
    )
    assert result.exit_code == 0, result.output
    assert seen[0].headers["Idempotency-Key"] == "pilot-key"
    assert json.loads(seen[0].content)["exclude_domains"] == ["excluded.com"]
    assert json.loads(result.stdout)["run_id"] == RUN_ID


def test_status_paginates(install_build_client: Callable[[Handler], None]) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.params["offset"] == "100"
        assert request.url.params["limit"] == "20"
        return httpx2.Response(200, json={"run_id": RUN_ID, "status": "needs_input", "max_actions": 24})

    install_build_client(handler)
    result = runner.invoke(app, ["prospecting", "status", RUN_ID, "--offset", "100", "--limit", "20"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["status"] == "needs_input"


def test_cancel_and_wait_preserve_terminal_outcomes(install_build_client: Callable[[Handler], None]) -> None:
    methods = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        methods.append(request.method)
        return httpx2.Response(200, json={"run_id": RUN_ID, "status": "cancelled", "max_actions": 24})

    install_build_client(handler)
    for command in ("cancel", "wait"):
        result = runner.invoke(app, ["prospecting", command, RUN_ID])
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["status"] == "cancelled"
    assert methods == ["DELETE", "GET"]
