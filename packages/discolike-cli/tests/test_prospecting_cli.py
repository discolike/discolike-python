from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import httpx2
import pytest
from typer.testing import CliRunner

import discolike_cli.prospecting as prospecting_cli
from discolike_cli._output import NEEDS_INPUT_EXIT_CODE
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
        methods.append((request.method, request.url.path))
        return httpx2.Response(200, json=run_payload("cancelled"))

    install_build_client(handler)
    for command in ("cancel", "wait"):
        result = runner.invoke(app, ["prospecting", command, RUN_ID])
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["status"] == "cancelled"
    assert methods == [("POST", f"/v1/prospecting/runs/{RUN_ID}/cancel"), ("GET", f"/v1/prospecting/runs/{RUN_ID}")]


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
    assert json.loads(seen[1].content) == {"plan_version": 2, "checkpoints": "ask"}
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


@pytest.mark.parametrize(("flags", "mode"), [([], "ask"), (["--auto"], "auto")])
def test_start_and_approve_ask_at_checkpoints_unless_auto(
    install_build_client: Callable[[Handler], None], flags: list[str], mode: str
) -> None:
    bodies = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(json.loads(request.content))
        return httpx2.Response(202, json=run_payload("queued"))

    install_build_client(handler)
    start = ["prospecting", "start", "--brief", "US logistics companies", "--idempotency-key", "mode", *flags]
    for command in (start, ["prospecting", "approve", RUN_ID, "--plan-version", "1", *flags]):
        result = runner.invoke(app, command)
        assert result.exit_code == 0, result.output
    assert [body["checkpoints"] for body in bodies] == [mode, mode]


PILOT_REPLIES = ["Run the full list", "Stop here"]
PILOT_SAMPLE = [{"domain": "fits.com", "name": "Fits", "company_fit": "Yes", "reason": "Runs a trucking fleet"}]
PILOT_QUESTION = "I checked the first 20 companies: 18 fit your criteria (90%). Here are some of them."


def _question_message(seq: int) -> dict:
    return message_payload() | {
        "seq": seq,
        "role": "agent",
        "kind": "question",
        "content": PILOT_QUESTION,
        "data": {"reason": "pilot", "suggested_replies": PILOT_REPLIES, "sample": PILOT_SAMPLE},
    }


def _emitted(stdout: str) -> dict:
    """CliRunner echoes typed input to stdout, which a real terminal does not; the JSON follows it."""
    return json.loads(stdout[stdout.index("{") :])


def _checkpoint_handler(seen: list[httpx2.Request], *, answer_seq: int = 20) -> Handler:
    """A run paused at the pilot whose question is past the first message page; any answer resumes it."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        answered = any(sent.method == "POST" for sent in seen)
        after = request.url.params.get("messages_after")
        if request.method == "POST":
            return httpx2.Response(202, json=message_payload() | {"seq": answer_seq})
        if after == str(answer_seq):
            ack = message_payload() | {"seq": answer_seq + 1, "role": "agent", "kind": "ack", "content": "On it."}
            return httpx2.Response(200, json=run_payload("running") | {"messages": [ack]})
        if after == "7":
            return httpx2.Response(200, json=run_payload("needs_input") | {"messages": [_question_message(8)]})
        if after is not None:
            return httpx2.Response(200, json=run_payload("needs_input"))
        if answered:
            return httpx2.Response(200, json=run_payload("completed"))
        paused = {"stop_reason": "pilot", "error": PILOT_QUESTION, "next_message_seq": 7}
        return httpx2.Response(200, json=run_payload("needs_input") | paused)

    return handler


@pytest.mark.parametrize(("typed", "posted"), [("1", "Run the full list"), ("Only fleets over 50 trucks", None)])
def test_wait_asks_at_a_checkpoint_and_keeps_waiting(
    install_build_client: Callable[[Handler], None],
    monkeypatch: pytest.MonkeyPatch,
    typed: str,
    posted: str | None,
) -> None:
    seen: list[httpx2.Request] = []
    install_build_client(_checkpoint_handler(seen))
    monkeypatch.setattr(prospecting_cli, "_is_interactive", lambda: True)

    result = runner.invoke(app, ["prospecting", "wait", RUN_ID], input=f"{typed}\n")

    assert result.exit_code == 0, result.output
    assert _emitted(result.stdout)["status"] == "completed"
    (message,) = [request for request in seen if request.method == "POST"]
    assert json.loads(message.content) == {"text": posted or typed}
    assert message.headers["Idempotency-Key"].startswith("cli-checkpoint-")
    for shown in (PILOT_QUESTION, "fits.com: Runs a trucking fleet", "1. Run the full list", "2. Stop here", "On it."):
        assert shown in result.stderr


def test_wait_reprompts_for_a_number_out_of_range(
    install_build_client: Callable[[Handler], None], monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[httpx2.Request] = []
    install_build_client(_checkpoint_handler(seen))
    monkeypatch.setattr(prospecting_cli, "_is_interactive", lambda: True)

    result = runner.invoke(app, ["prospecting", "wait", RUN_ID], input="3\n2\n")

    assert result.exit_code == 0, result.output
    (message,) = [request for request in seen if request.method == "POST"]
    assert json.loads(message.content) == {"text": "Stop here"}


@pytest.mark.parametrize(("interactive", "flags"), [(False, []), (True, ["--no-input"])])
def test_wait_without_a_terminal_reports_the_checkpoint_and_exits_needs_input(
    install_build_client: Callable[[Handler], None],
    monkeypatch: pytest.MonkeyPatch,
    interactive: bool,
    flags: list[str],
) -> None:
    seen: list[httpx2.Request] = []
    install_build_client(_checkpoint_handler(seen))
    monkeypatch.setattr(prospecting_cli, "_is_interactive", lambda: interactive)

    result = runner.invoke(app, ["prospecting", "wait", RUN_ID, *flags])

    assert result.exit_code == NEEDS_INPUT_EXIT_CODE
    assert json.loads(result.stdout)["stop_reason"] == "pilot"
    envelope = json.loads(result.stderr.splitlines()[-1])
    assert envelope == {
        "error": "NeedsInput",
        "code": "needs_input",
        "message": PILOT_QUESTION,
        "status_code": None,
        "exit_code": NEEDS_INPUT_EXIT_CODE,
        "run_id": RUN_ID,
        "stop_reason": "pilot",
        "suggested_replies": PILOT_REPLIES,
        "sample": PILOT_SAMPLE,
    }
    assert all(request.method == "GET" for request in seen)


def test_wait_returns_other_needs_input_pauses_unchanged(
    install_build_client: Callable[[Handler], None], monkeypatch: pytest.MonkeyPatch
) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json=run_payload("needs_input") | {"stop_reason": "question"})

    install_build_client(handler)
    monkeypatch.setattr(prospecting_cli, "_is_interactive", lambda: False)

    result = runner.invoke(app, ["prospecting", "wait", RUN_ID])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["stop_reason"] == "question"


def test_start_reads_customers_from_a_file(install_build_client: Callable[[Handler], None], tmp_path: Path) -> None:
    customers = tmp_path / "customers.csv"
    customers.write_text("domain\nAcme.com\nwww.example.com\nacme.com\n")
    bodies = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(json.loads(request.content))
        return httpx2.Response(202, json=run_payload("drafting"))

    install_build_client(handler)
    result = runner.invoke(
        app,
        [
            "prospecting",
            "start",
            "--brief",
            "Lookalikes of our customers and their CTOs",
            "--idempotency-key",
            "seeded",
            "--customers-file",
            str(customers),
        ],
    )
    assert result.exit_code == 0, result.output
    assert bodies[0]["customer_domains"] == ["acme.com", "example.com"]


def test_approve_sends_the_chosen_segments_and_results_grouping(
    install_build_client: Callable[[Handler], None],
) -> None:
    bodies = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(json.loads(request.content))
        return httpx2.Response(202, json=run_payload("queued"))

    install_build_client(handler)
    chosen = runner.invoke(
        app,
        [
            "prospecting",
            "approve",
            RUN_ID,
            "--plan-version",
            "1",
            "--seed-segment",
            "1",
            "--seed-segment",
            "2",
            "--segment",
        ],
    )
    default = runner.invoke(app, ["prospecting", "approve", RUN_ID, "--plan-version", "1"])
    assert chosen.exit_code == default.exit_code == 0, chosen.output + default.output
    assert bodies == [
        {"plan_version": 1, "checkpoints": "ask", "seed_segments": [1, 2], "segment": True},
        {"plan_version": 1, "checkpoints": "ask"},
    ]
