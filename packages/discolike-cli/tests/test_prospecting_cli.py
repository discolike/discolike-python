from __future__ import annotations

import json
from collections.abc import Callable

import httpx2
import pytest
from typer.testing import CliRunner

from discolike_cli.main import app
from discolike_testkit import Handler
from discolike_testkit.prospecting import message_payload
from discolike_testkit.prospecting import run_payload
from discolike_testkit.prospecting import summary_payload

runner = CliRunner()
RUN_ID = "00000000-0000-0000-0000-000000000001"


def test_start_forwards_key_and_brief(install_build_client: Callable[[Handler], None]) -> None:
    seen = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(202, json=run_payload("queued"))

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
        return httpx2.Response(200, json=run_payload("needs_input"))

    install_build_client(handler)
    result = runner.invoke(app, ["prospecting", "status", RUN_ID, "--offset", "100", "--limit", "20"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["status"] == "needs_input"


def test_status_lists_every_saved_query_part(install_build_client: Callable[[Handler], None]) -> None:
    other_query_id = "00000000-0000-0000-0000-000000000002"

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200, json=run_payload("completed") | {"saved_query_id": RUN_ID, "saved_query_ids": [RUN_ID, other_query_id]}
        )

    install_build_client(handler)
    result = runner.invoke(app, ["prospecting", "status", RUN_ID])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["saved_query_ids"] == [RUN_ID, other_query_id]


def test_cancel_and_wait_preserve_terminal_outcomes(install_build_client: Callable[[Handler], None]) -> None:
    methods = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        methods.append(request.method)
        return httpx2.Response(200, json=run_payload("cancelled"))

    install_build_client(handler)
    for command in ("cancel", "wait"):
        result = runner.invoke(app, ["prospecting", command, RUN_ID])
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["status"] == "cancelled"
    assert methods == ["DELETE", "GET"]


def test_start_omits_unspecified_quantities_and_caps(install_build_client: Callable[[Handler], None]) -> None:
    seen = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(json.loads(request.content))
        return httpx2.Response(202, json=run_payload("queued"))

    install_build_client(handler)
    result = runner.invoke(
        app,
        [
            "prospecting",
            "start",
            "--brief",
            "Find 1000 software companies and three founders each",
            "--idempotency-key",
            "counts",
        ],
    )
    assert result.exit_code == 0, result.output
    for key in ("target_companies", "contacts_per_company", "max_candidates", "max_actions"):
        assert key not in seen[0]


def test_chat_commands_send_exact_payloads(install_build_client: Callable[[Handler], None]) -> None:
    seen = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        if request.url.path.endswith("/messages"):
            return httpx2.Response(202, json=message_payload())
        if request.url.path.endswith("/runs"):
            return httpx2.Response(200, json=[summary_payload()])
        return httpx2.Response(200, json=run_payload("proposed"))

    install_build_client(handler)
    commands = [
        ["list", "--before", RUN_ID],
        ["approve", RUN_ID, "--plan-version", "2"],
        ["message", RUN_ID, "--text", "Make it 100 companies", "--idempotency-key", "cli-message"],
        ["status", RUN_ID, "--events-after", "12", "--messages-after", "8", "--limit", "500"],
        ["wait", RUN_ID],
    ]
    for command in commands:
        result = runner.invoke(app, ["prospecting", *command])
        assert result.exit_code == 0, result.output
    assert dict(seen[0].url.params) == {"limit": "20", "before": RUN_ID}
    assert json.loads(seen[1].content) == {"plan_version": 2}
    assert json.loads(seen[2].content) == {"text": "Make it 100 companies"}
    assert seen[2].headers["Idempotency-Key"] == "cli-message"
    assert dict(seen[3].url.params) == {"offset": "0", "limit": "500", "events_after": "12", "messages_after": "8"}
    assert len(seen) == 5


@pytest.mark.parametrize(
    "arguments",
    [
        ["approve", RUN_ID],
        ["message", RUN_ID, "--text", "Continue"],
        ["list", "--limit", "51"],
        ["list", "--before", "not-a-uuid"],
        ["status", RUN_ID, "--messages-after", "-1"],
    ],
)
def test_chat_commands_validate_before_network(
    install_build_client: Callable[[Handler], None], arguments: list[str]
) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        pytest.fail("invalid command must not reach the network")

    install_build_client(handler)
    assert runner.invoke(app, ["prospecting", *arguments]).exit_code == 2


@pytest.mark.parametrize(("target", "contacts", "candidates", "actions"), [(25, 2, 0, 0), (10000, 5, 100000, 10000)])
def test_explicit_defaults_and_larger_caps_are_preserved(
    install_build_client: Callable[[Handler], None], target: int, contacts: int, candidates: int, actions: int
) -> None:
    seen = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(json.loads(request.content))
        return httpx2.Response(202, json=run_payload())

    install_build_client(handler)
    result = runner.invoke(
        app,
        [
            "prospecting",
            "start",
            "--brief",
            "Find software companies and founders",
            "--idempotency-key",
            "explicit",
            "--target-companies",
            str(target),
            "--contacts-per-company",
            str(contacts),
            "--max-candidates",
            str(candidates),
            "--max-actions",
            str(actions),
        ],
    )
    assert result.exit_code == 0, result.output
    assert {
        key: seen[0][key] for key in ("target_companies", "contacts_per_company", "max_candidates", "max_actions")
    } == {
        "target_companies": target,
        "contacts_per_company": contacts,
        "max_candidates": candidates,
        "max_actions": actions,
    }
