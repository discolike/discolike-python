from __future__ import annotations

import json
import pathlib
import time
from collections.abc import Callable

import httpx2
import pydantic
import pytest
from typer.testing import CliRunner

from discolike.requests import FindEmailBatchRequest
from discolike_cli.main import app
from discolike_testkit import Handler

runner = CliRunner()


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "sleep", lambda seconds: None)


FOUND_RESULT = {
    "first_name": "Jane",
    "last_name": "Doe",
    "domain": "acme.com",
    "status": "found",
    "result": {"email": "jane.doe@acme.com", "pattern": "{first}.{last}", "valid": True},
}


def test_email_find_without_wait_prints_job_hint(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, httpx2.Request] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["request"] = request
        return httpx2.Response(200, json={"job_id": "ej-1"})

    install_build_client(handler)
    result = runner.invoke(app, ["email", "find", "Jane", "Doe", "acme.com"])
    assert result.exit_code == 0, result.output
    request = captured["request"]
    assert request.url.path == "/v1/email/find"
    assert json.loads(request.content) == {"first_name": "Jane", "last_name": "Doe", "domain": "acme.com"}
    payload = json.loads(result.stdout)
    assert payload["job_id"] == "ej-1"
    assert "discolike email job ej-1" in payload["hint"]


def test_email_find_with_wait_polls_to_completion(install_build_client: Callable[[Handler], None]) -> None:
    statuses = iter(
        [
            httpx2.Response(200, json={"job_id": "ej-2", "status": "processing"}),
            httpx2.Response(200, json={"job_id": "ej-2", "status": "completed", "result": FOUND_RESULT}),
        ]
    )

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/v1/email/find":
            return httpx2.Response(200, json={"job_id": "ej-2"})
        assert request.url.path == "/v1/email/jobs/ej-2"
        return next(statuses)

    install_build_client(handler)
    result = runner.invoke(app, ["email", "find", "Jane", "Doe", "acme.com", "--wait", "--timeout", "5"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["status"] == "found"
    assert payload["result"]["email"] == "jane.doe@acme.com"
    assert "status: processing" in result.stderr


def test_email_find_batch_from_csv_file(
    tmp_path: pathlib.Path, install_build_client: Callable[[Handler], None]
) -> None:
    contacts_file = tmp_path / "contacts.csv"
    contacts_file.write_text("first_name,last_name,domain\nJane,Doe,acme.com\nJohn,Smith,beta.com\n")
    captured: dict[str, httpx2.Request] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["request"] = request
        return httpx2.Response(200, json={"batch_id": "eb-1"})

    install_build_client(handler)
    result = runner.invoke(app, ["email", "find-batch", "--contacts-file", str(contacts_file)])
    assert result.exit_code == 0, result.output
    request = captured["request"]
    assert request.url.path == "/v1/email/find/batch"
    assert json.loads(request.content) == {
        "requests": [
            {"first_name": "Jane", "last_name": "Doe", "domain": "acme.com"},
            {"first_name": "John", "last_name": "Smith", "domain": "beta.com"},
        ]
    }
    payload = json.loads(result.stdout)
    assert payload["batch_id"] == "eb-1"
    assert "discolike email results eb-1" in payload["hint"]


def test_email_find_batch_from_inline_contacts(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, httpx2.Request] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["request"] = request
        return httpx2.Response(200, json={"batch_id": "eb-2"})

    install_build_client(handler)
    result = runner.invoke(
        app,
        ["email", "find-batch", "--contact", "Jane,Doe,acme.com", "--contact", "John, Smith, beta.com"],
    )
    assert result.exit_code == 0, result.output
    body = json.loads(captured["request"].content)
    assert body["requests"] == [
        {"first_name": "Jane", "last_name": "Doe", "domain": "acme.com"},
        {"first_name": "John", "last_name": "Smith", "domain": "beta.com"},
    ]


def test_email_find_batch_with_wait_polls_results(install_build_client: Callable[[Handler], None]) -> None:
    results_pages = iter(
        [
            httpx2.Response(200, json={"batch_id": "eb-3", "total": 1, "completed": 0, "failed": 0, "results": []}),
            httpx2.Response(
                200,
                json={
                    "batch_id": "eb-3",
                    "total": 1,
                    "completed": 1,
                    "failed": 0,
                    "results": [{"job_id": "ej-9", "status": "completed", "result": FOUND_RESULT}],
                },
            ),
        ]
    )

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/v1/email/find/batch":
            return httpx2.Response(200, json={"batch_id": "eb-3"})
        assert request.url.path == "/v1/email/batch/eb-3/results"
        return next(results_pages)

    install_build_client(handler)
    result = runner.invoke(
        app,
        ["email", "find-batch", "--contact", "Jane,Doe,acme.com", "--wait", "--timeout", "5"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["completed"] == 1
    assert payload["results"][0]["result"]["result"]["email"] == "jane.doe@acme.com"
    assert "progress: 0/1 completed, 0 failed" in result.stderr


@pytest.mark.parametrize(
    "args",
    [
        [],  # neither source given
        ["--contact", "Jane,Doe"],  # too few fields
        ["--contact", "Jane,,acme.com"],  # empty field
    ],
)
def test_email_find_batch_bad_contacts_exit_2(args: list[str], install_build_client: Callable[[Handler], None]) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"batch_id": "eb-4"})

    install_build_client(handler)
    result = runner.invoke(app, ["email", "find-batch", *args])
    assert result.exit_code == 2


def test_email_find_batch_missing_csv_columns_exits_2(
    tmp_path: pathlib.Path, install_build_client: Callable[[Handler], None]
) -> None:
    contacts_file = tmp_path / "contacts.csv"
    contacts_file.write_text("first,last,site\nJane,Doe,acme.com\n")

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"batch_id": "eb-5"})

    install_build_client(handler)
    result = runner.invoke(app, ["email", "find-batch", "--contacts-file", str(contacts_file)])
    assert result.exit_code == 2
    assert "domain" in result.output


def test_email_find_batch_rejects_empty_csv_cell_before_any_request(
    tmp_path: pathlib.Path, install_build_client: Callable[[Handler], None]
) -> None:
    contacts_file = tmp_path / "contacts.csv"
    contacts_file.write_text("first_name,last_name,domain\nJane,Doe,acme.com\nJohn,Smith,\n")
    calls: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(request)
        return httpx2.Response(200, json={"batch_id": "eb-5"})

    install_build_client(handler)
    result = runner.invoke(app, ["email", "find-batch", "--contacts-file", str(contacts_file)])
    assert result.exit_code == 2
    assert "row 3" in result.output
    assert "domain" in result.output
    assert calls == []


def test_email_find_batch_over_500_contacts_exits_2(
    tmp_path: pathlib.Path, install_build_client: Callable[[Handler], None]
) -> None:
    rows = "\n".join(f"Jane{i},Doe,acme.com" for i in range(501))
    contacts_file = tmp_path / "contacts.csv"
    contacts_file.write_text(f"first_name,last_name,domain\n{rows}\n")

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"batch_id": "eb-6"})

    install_build_client(handler)
    result = runner.invoke(app, ["email", "find-batch", "--contacts-file", str(contacts_file)])
    assert result.exit_code == 2
    assert "500" in result.output


def test_find_email_batch_request_rejects_more_than_500_requests() -> None:
    requests = [{"first_name": "Jane", "last_name": "Doe", "domain": "acme.com"}] * 501
    with pytest.raises(pydantic.ValidationError):
        FindEmailBatchRequest.model_validate({"requests": requests})


def test_email_results_without_wait_returns_partial_snapshot(
    install_build_client: Callable[[Handler], None],
) -> None:
    captured: dict[str, httpx2.Request] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["request"] = request
        return httpx2.Response(
            200,
            json={"batch_id": "eb-7", "total": 2, "completed": 1, "failed": 0, "results": [{"status": "completed"}]},
        )

    install_build_client(handler)
    result = runner.invoke(app, ["email", "results", "eb-7"])
    assert result.exit_code == 0, result.output
    assert captured["request"].url.path == "/v1/email/batch/eb-7/results"
    payload = json.loads(result.stdout)
    assert payload["batch_id"] == "eb-7"
    assert payload["completed"] == 1


def test_email_results_verify_kind_decodes_validation_output(
    install_build_client: Callable[[Handler], None],
) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/v1/email/batch/eb-8/results"
        return httpx2.Response(
            200,
            json={
                "batch_id": "eb-8",
                "total": 1,
                "completed": 1,
                "failed": 0,
                "results": [
                    {
                        "job_id": "ej-8",
                        "status": "completed",
                        "result": {"email": "jane@acme.com", "status": "valid", "reason": "deliverable"},
                    }
                ],
            },
        )

    install_build_client(handler)
    result = runner.invoke(app, ["email", "results", "eb-8", "--kind", "verify"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["results"][0]["result"]["reason"] == "deliverable"


def test_email_results_invalid_kind_exits_2(install_build_client: Callable[[Handler], None]) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={})

    install_build_client(handler)
    result = runner.invoke(app, ["email", "results", "eb-9", "--kind", "bogus"])
    assert result.exit_code == 2


def test_email_job_prints_current_status(install_build_client: Callable[[Handler], None]) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/v1/email/jobs/ej-5"
        return httpx2.Response(200, json={"job_id": "ej-5", "status": "processing"})

    install_build_client(handler)
    result = runner.invoke(app, ["email", "job", "ej-5"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["job_id"] == "ej-5"
    assert payload["status"] == "processing"


def test_email_job_unauthorized_exits_3(install_build_client: Callable[[Handler], None]) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(401, json={"detail": "invalid key"})

    install_build_client(handler)
    result = runner.invoke(app, ["email", "job", "ej-6"])
    assert result.exit_code == 3
    payload = json.loads(result.stderr)
    assert payload["error"] == "AuthenticationError"
