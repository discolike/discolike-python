from __future__ import annotations

import json
import sys
from collections.abc import Callable

import pydantic
import pytest
import typer

from discolike import AuthenticationError
from discolike import RateLimitError
from discolike import ServerError
from discolike import ValidationError
from discolike.requests import DiscoverParams
from discolike.requests import MatchCompanyParams
from discolike.resources.discovery import Company
from discolike_cli._output import EXIT_CODES
from discolike_cli._output import build_request
from discolike_cli._output import emit
from discolike_cli._output import fail
from discolike_cli._output import handle_errors
from discolike_cli._output import run_job


def test_emit_dict_prints_json(capsys: pytest.CaptureFixture[str]) -> None:
    emit({"a": 1, "b": "two"})
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"a": 1, "b": "two"}


def test_emit_list_of_dicts_prints_json_when_not_tty(capsys: pytest.CaptureFixture[str]) -> None:
    emit([{"domain": "a.com"}, {"domain": "b.com"}])
    captured = capsys.readouterr()
    assert json.loads(captured.out) == [{"domain": "a.com"}, {"domain": "b.com"}]


def test_emit_model_converts_to_dict(capsys: pytest.CaptureFixture[str]) -> None:
    company = Company(domain="acme.com", name="Acme", similarity=0.9, score=80, start_date=None)
    emit(company)
    captured = capsys.readouterr()
    assert json.loads(captured.out) == company.to_dict()


def test_emit_list_of_models_converts_each_to_dict(capsys: pytest.CaptureFixture[str]) -> None:
    companies = [Company(domain="acme.com"), Company(domain="beta.com")]
    emit(companies)
    captured = capsys.readouterr()
    assert json.loads(captured.out) == [c.to_dict() for c in companies]


def test_emit_table_flag_renders_rich_table(capsys: pytest.CaptureFixture[str]) -> None:
    emit([{"domain": "acme.com", "score": 80}, {"domain": "beta.com", "score": 60}], fmt="table")
    captured = capsys.readouterr()
    assert "domain" in captured.out
    assert "acme.com" in captured.out
    with pytest.raises(json.JSONDecodeError):
        json.loads(captured.out)


def test_emit_defaults_to_json_when_stdout_not_a_tty(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False, raising=False)
    emit([{"domain": "acme.com"}])
    captured = capsys.readouterr()
    assert json.loads(captured.out) == [{"domain": "acme.com"}]


def test_emit_uses_table_when_tty_and_data_qualifies(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True, raising=False)
    emit([{"domain": "acme.com"}])
    captured = capsys.readouterr()
    with pytest.raises(json.JSONDecodeError):
        json.loads(captured.out)
    assert "domain" in captured.out


def test_emit_table_flag_falls_back_to_json_for_empty_list(capsys: pytest.CaptureFixture[str]) -> None:
    emit([], fmt="table")
    captured = capsys.readouterr()
    assert json.loads(captured.out) == []


def test_emit_table_renders_scalar_columns_and_drops_nested_ones(capsys: pytest.CaptureFixture[str]) -> None:
    emit(
        [
            {"domain": "acme.com", "score": 80, "address": {"city": "Perth"}, "phones": ["+1555"]},
            {"domain": "beta.com", "score": 60, "address": {"city": "Austin"}, "phones": []},
        ],
        fmt="table",
    )
    captured = capsys.readouterr()
    with pytest.raises(json.JSONDecodeError):
        json.loads(captured.out)
    assert "domain" in captured.out
    assert "acme.com" in captured.out
    assert "address" not in captured.out
    assert "phones" not in captured.out


def test_emit_table_drops_column_nested_in_any_row(capsys: pytest.CaptureFixture[str]) -> None:
    emit(
        [
            {"domain": "acme.com", "status": "active"},
            {"domain": "beta.com", "status": {"status": "active", "confidence": 1.0}},
        ],
        fmt="table",
    )
    captured = capsys.readouterr()
    assert "domain" in captured.out
    assert "status" not in captured.out


def test_emit_table_truncates_long_cells(capsys: pytest.CaptureFixture[str]) -> None:
    emit([{"domain": "acme.com", "description": "x" * 500}], fmt="table")
    captured = capsys.readouterr()
    assert "…" in captured.out
    assert "x" * 200 not in captured.out.replace("\n", "")


def test_emit_table_renders_none_as_empty_cell(capsys: pytest.CaptureFixture[str]) -> None:
    emit([{"domain": "acme.com", "redirect_domain": None}], fmt="table")
    captured = capsys.readouterr()
    assert "None" not in captured.out


def test_emit_table_caps_column_count(capsys: pytest.CaptureFixture[str]) -> None:
    emit([{f"col{i}": i for i in range(12)}], fmt="table")
    captured = capsys.readouterr()
    assert "col7" in captured.out
    assert "col8" not in captured.out


def test_emit_table_flag_falls_back_to_json_when_no_scalar_columns(capsys: pytest.CaptureFixture[str]) -> None:
    emit([{"tags": ["a", "b"]}], fmt="table")
    captured = capsys.readouterr()
    assert json.loads(captured.out) == [{"tags": ["a", "b"]}]


@pytest.mark.parametrize(
    ("exc", "code"),
    [
        (ValidationError("bad input"), 2),
        (AuthenticationError("no key"), 3),
        (RateLimitError("slow down", retry_after=3), 4),
        (ServerError("boom"), 1),
    ],
)
def test_exit_codes_mapping(exc: Exception, code: int) -> None:
    assert EXIT_CODES.get(type(exc), 1) == code


def test_fail_writes_stderr_json_and_returns_typer_exit(capsys: pytest.CaptureFixture[str]) -> None:
    exc = ValidationError("bad field", status_code=400)
    result = fail(exc)
    assert isinstance(result, typer.Exit)
    assert result.exit_code == 2
    captured = capsys.readouterr()
    payload = json.loads(captured.err)
    assert payload == {"error": "ValidationError", "message": "bad field", "status_code": 400}
    assert captured.out == ""


def test_fail_rate_limit_includes_retry_after(capsys: pytest.CaptureFixture[str]) -> None:
    exc = RateLimitError("slow down", status_code=429, retry_after=3.5)
    result = fail(exc)
    assert result.exit_code == 4
    payload = json.loads(capsys.readouterr().err)
    assert payload["retry_after"] == 3.5


def test_fail_rate_limit_without_retry_after_omits_key(capsys: pytest.CaptureFixture[str]) -> None:
    exc = RateLimitError("slow down", status_code=429, retry_after=None)
    fail(exc)
    payload = json.loads(capsys.readouterr().err)
    assert "retry_after" not in payload


def test_fail_unmapped_error_defaults_to_exit_code_one(capsys: pytest.CaptureFixture[str]) -> None:
    exc = ServerError("boom", status_code=500)
    result = fail(exc)
    assert result.exit_code == 1


def test_handle_errors_decorator_reraises_as_typer_exit(capsys: pytest.CaptureFixture[str]) -> None:
    @handle_errors
    def boom() -> None:
        raise AuthenticationError("nope")

    with pytest.raises(typer.Exit) as exc_info:
        boom()
    assert exc_info.value.exit_code == 3
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"] == "AuthenticationError"


def test_handle_errors_passes_through_return_value() -> None:
    @handle_errors
    def ok(x: int, *, y: int) -> int:
        return x + y

    assert ok(1, y=2) == 3


class _FakeJobStatus:
    def __init__(self, *, progress: int, results: object) -> None:
        self.progress = progress
        self.results = results

    def to_dict(self) -> dict[str, object]:
        return {"progress": self.progress, "results": self.results}


class _FakeJob:
    def __init__(self, *, task_id: str, task_family: str, final: _FakeJobStatus) -> None:
        self.task_id = task_id
        self.task_family = task_family
        self._final = final
        self.wait_calls: list[dict[str, object]] = []

    def wait(self, *, timeout: float, on_poll: Callable[[_FakeJobStatus], None] | None = None) -> _FakeJobStatus:
        self.wait_calls.append({"timeout": timeout})
        if on_poll is not None:
            on_poll(_FakeJobStatus(progress=50, results=None))
        return self._final


def test_run_job_without_wait_emits_task_info(capsys: pytest.CaptureFixture[str]) -> None:
    job = _FakeJob(task_id="t1", task_family="discogen", final=_FakeJobStatus(progress=100, results=None))
    run_job(job, wait=False, timeout=30.0)
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["task_id"] == "t1"
    assert payload["task_family"] == "discogen"
    assert "t1" in payload["hint"]
    assert job.wait_calls == []


def test_run_job_with_wait_emits_final_results_and_progress(capsys: pytest.CaptureFixture[str]) -> None:
    final = _FakeJobStatus(progress=100, results=[{"domain": "acme.com"}])
    job = _FakeJob(task_id="t2", task_family="discogen", final=final)
    run_job(job, wait=True, timeout=30.0)
    captured = capsys.readouterr()
    assert json.loads(captured.out) == [{"domain": "acme.com"}]
    assert "progress: 50%" in captured.err
    assert job.wait_calls == [{"timeout": 30.0}]


def test_run_job_with_wait_emits_full_status_when_no_results(capsys: pytest.CaptureFixture[str]) -> None:
    final = _FakeJobStatus(progress=100, results=None)
    job = _FakeJob(task_id="t3", task_family="segment", final=final)
    run_job(job, wait=True, timeout=30.0)
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"progress": 100, "results": None}


def test_build_request_wraps_a_bare_string_for_list_fields() -> None:
    request = build_request(DiscoverParams, {"subdomain": "shop", "country": ["DE"], "icp_prompt": "X"})
    assert request.to_wire() == {"subdomain": ["shop"], "country": ["DE"], "icp_prompt": "X"}


def test_build_request_coerces_scalar_strings_from_param() -> None:
    request = build_request(DiscoverParams, {"min_similarity": "50", "redirect": "true"})
    assert request.to_wire() == {"min_similarity": 50, "redirect": True}


def test_build_request_passes_unknown_keys_through() -> None:
    assert build_request(DiscoverParams, {"future_flag": "on"}).to_wire() == {"future_flag": "on"}


def test_build_request_raises_pydantic_validation_error_on_bad_values() -> None:
    with pytest.raises(pydantic.ValidationError, match="min_similarity"):
        build_request(DiscoverParams, {"min_similarity": "200"})


def test_handle_errors_maps_pydantic_validation_error_to_exit_2(capsys: pytest.CaptureFixture[str]) -> None:
    @handle_errors
    def bad() -> None:
        MatchCompanyParams.model_validate({"min_match_confidence": 10})

    with pytest.raises(typer.Exit) as exc_info:
        bad()
    assert exc_info.value.exit_code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"] == "ValidationError"
    assert payload["status_code"] is None
    assert "name" in payload["message"]
    assert "min_match_confidence" in payload["message"]
