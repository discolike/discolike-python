"""--domains-file / --params-file / --exclude-domains-file on the volume commands (issue #23)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2
import pytest
from typer.testing import CliRunner

from discolike_cli.main import app
from discolike_testkit import Handler
from discolike_testkit import plain_output

runner = CliRunner()


@pytest.fixture
def domains_file(tmp_path: Path) -> Path:
    path = tmp_path / "companies.csv"
    path.write_text("domain,name\nacme.com,Acme\nbeta.io,Beta\n")
    return path


def _capture_json(captured: dict[str, Any], response: object) -> Handler:
    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["path"] = request.url.path
        captured["params"] = request.url.params
        captured["body"] = json.loads(request.content) if request.content else None
        return httpx2.Response(200, json=response)

    return handler


def test_create_exclusion_list_merges_domains_file_with_inline(
    install_build_client: Callable[[Handler], None], domains_file: Path
) -> None:
    captured: dict[str, Any] = {}
    install_build_client(_capture_json(captured, {"query_id": "q1"}))
    result = runner.invoke(
        app,
        [
            "queries",
            "create-exclusion-list",
            "--name",
            "L",
            "--domain",
            "gamma.co",
            "--domains-file",
            str(domains_file),
        ],
    )
    assert result.exit_code == 0, result.output
    assert captured["body"] == {"query_name": "L", "domains": ["gamma.co", "acme.com", "beta.io"]}


def test_contacts_discover_domains_file(install_build_client: Callable[[Handler], None], domains_file: Path) -> None:
    captured: dict[str, Any] = {}
    install_build_client(_capture_json(captured, {"results": {}}))
    result = runner.invoke(app, ["contacts", "discover", "--domains-file", str(domains_file)])
    assert result.exit_code == 0, result.output
    assert captured["body"] == {"domain": ["acme.com", "beta.io"]}


def test_contacts_search_domains_file(install_build_client: Callable[[Handler], None], domains_file: Path) -> None:
    captured: dict[str, Any] = {}
    install_build_client(_capture_json(captured, []))
    result = runner.invoke(app, ["contacts", "search", "--domains-file", str(domains_file)])
    assert result.exit_code == 0, result.output
    assert captured["params"].get_list("domain") == ["acme.com", "beta.io"]


def test_contacts_count_domains_file(install_build_client: Callable[[Handler], None], domains_file: Path) -> None:
    captured: dict[str, Any] = {}
    install_build_client(_capture_json(captured, {"count": 3}))
    result = runner.invoke(app, ["contacts", "count", "--domains-file", str(domains_file)])
    assert result.exit_code == 0, result.output
    assert captured["params"].get_list("domain") == ["acme.com", "beta.io"]


def test_contacts_generate_domains_file_replaces_required_domain(
    install_build_client: Callable[[Handler], None], domains_file: Path
) -> None:
    captured: dict[str, Any] = {}
    install_build_client(_capture_json(captured, {"task_id": "t1"}))
    result = runner.invoke(app, ["contacts", "generate", "--icp-text", "X", "--domains-file", str(domains_file)])
    assert result.exit_code == 0, result.output
    assert captured["body"] == {"icp_text": "X", "domains": ["acme.com", "beta.io"]}


def test_contacts_generate_requires_domain_or_file(install_build_client: Callable[[Handler], None]) -> None:
    install_build_client(_capture_json({}, {"task_id": "t1"}))
    result = runner.invoke(app, ["contacts", "generate", "--icp-text", "X"])
    assert result.exit_code != 0
    assert "--domain or --domains-file" in plain_output(result.output)


def test_discogen_run_domains_file(install_build_client: Callable[[Handler], None], domains_file: Path) -> None:
    captured: dict[str, Any] = {}
    install_build_client(_capture_json(captured, {"task_id": "t1"}))
    result = runner.invoke(app, ["discogen", "run", "--query", "Q", "--domains-file", str(domains_file)])
    assert result.exit_code == 0, result.output
    assert captured["body"] == {"query": "Q", "domains": ["acme.com", "beta.io"]}


def test_validate_icp_accepts_domains_file_alias(
    install_build_client: Callable[[Handler], None], domains_file: Path
) -> None:
    captured: dict[str, Any] = {}
    install_build_client(_capture_json(captured, {"task_id": "t1"}))
    result = runner.invoke(app, ["validate-icp", "--icp", "X", "--domains-file", str(domains_file)])
    assert result.exit_code == 0, result.output
    assert captured["body"] == {"icp_text": "X", "domains": ["acme.com", "beta.io"]}


def test_discover_params_file_under_param_under_flags(
    install_build_client: Callable[[Handler], None], tmp_path: Path
) -> None:
    form = tmp_path / "form.json"
    form.write_text(json.dumps({"country": ["US"], "variance": "LOW", "min_similarity": 10, "consensus": 3}))
    captured: dict[str, Any] = {}
    install_build_client(_capture_json(captured, []))
    result = runner.invoke(
        app,
        ["discover", "--params-file", str(form), "--param", "min_similarity=50", "--variance", "HIGH"],
    )
    assert result.exit_code == 0, result.output
    params = captured["params"]
    assert params.get_list("country") == ["US"]
    assert params.get("variance") == "HIGH"
    assert params.get("min_similarity") == "50"
    assert params.get("consensus") == "3"


def test_discover_params_file_is_validated_locally(
    install_build_client: Callable[[Handler], None], tmp_path: Path
) -> None:
    form = tmp_path / "form.json"
    form.write_text(json.dumps({"variance": "BOGUS"}))
    calls: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(request.url.path)
        return httpx2.Response(200, json=[])

    install_build_client(handler)
    result = runner.invoke(app, ["discover", "--params-file", str(form)])
    assert result.exit_code == 2
    assert "ValidationError" in result.output
    assert calls == []


def test_count_params_file(install_build_client: Callable[[Handler], None], tmp_path: Path) -> None:
    form = tmp_path / "form.json"
    form.write_text(json.dumps({"country": ["DE"]}))
    captured: dict[str, Any] = {}
    install_build_client(_capture_json(captured, {"count": 1}))
    result = runner.invoke(app, ["count", "--params-file", str(form)])
    assert result.exit_code == 0, result.output
    assert captured["params"].get_list("country") == ["DE"]


@pytest.mark.parametrize("command", ["discover", "search", "count"])
def test_contacts_params_file(install_build_client: Callable[[Handler], None], tmp_path: Path, command: str) -> None:
    form = tmp_path / "form.json"
    form.write_text(json.dumps({"seniority": ["executive"], "negate_summary": "bookkeeping"}))
    captured: dict[str, Any] = {}
    response: object = {"results": {}} if command == "discover" else ([] if command == "search" else {"count": 0})
    install_build_client(_capture_json(captured, response))
    result = runner.invoke(app, ["contacts", command, "--params-file", str(form), "--param", "seniority=vp"])
    assert result.exit_code == 0, result.output
    if command == "discover":
        assert captured["body"] == {"seniority": ["vp"], "negate_summary": "bookkeeping"}
    else:
        assert captured["params"].get_list("seniority") == ["vp"]
        assert captured["params"].get("negate_summary") == "bookkeeping"


def test_discover_exclude_domains_file_merges_with_inline(
    install_build_client: Callable[[Handler], None], domains_file: Path
) -> None:
    captured: dict[str, Any] = {}
    install_build_client(_capture_json(captured, []))
    result = runner.invoke(
        app,
        ["discover", "--icp-prompt", "X", "--exclude-domain", "gamma.co", "--exclude-domains-file", str(domains_file)],
    )
    assert result.exit_code == 0, result.output
    assert captured["params"].get_list("exclude_domain") == ["gamma.co", "acme.com", "beta.io"]


def test_discover_exclude_domains_file_over_cap_fails_before_call(
    install_build_client: Callable[[Handler], None], tmp_path: Path
) -> None:
    path = tmp_path / "many.txt"
    path.write_text("\n".join(f"d{i}.com" for i in range(101)))
    calls: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(request.url.path)
        return httpx2.Response(200, json=[])

    install_build_client(handler)
    result = runner.invoke(app, ["discover", "--icp-prompt", "X", "--exclude-domains-file", str(path)])
    assert result.exit_code == 2
    assert "ValidationError" in result.output
    assert calls == []
