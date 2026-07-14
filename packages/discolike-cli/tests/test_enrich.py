from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest
from typer.testing import CliRunner

import discolike_cli.main as cli_main
from conftest import make_client
from discolike_cli.main import app

runner = CliRunner()


def _install_build_client(monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response]) -> None:
    monkeypatch.setattr(cli_main, "build_client", lambda **kwargs: make_client(handler))


def test_validate_icp_with_domain_options_posts_json(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"task_id": "vi-1"})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(
        app,
        ["validate-icp", "--icp", "VPs of Marketing", "--domain", "acme.com", "--domain", "beta.com"],
    )
    assert result.exit_code == 0, result.output
    assert captured["path"] == "/v1/validate/icp"
    assert captured["body"] == {
        "icp_text": "VPs of Marketing",
        "domains": ["acme.com", "beta.com"],
    }
    payload = json.loads(result.stdout)
    assert payload["task_id"] == "vi-1"


def test_validate_icp_sends_web_search_when_passed(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"task_id": "vi-1b"})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(
        app,
        ["validate-icp", "--icp", "VPs of Marketing", "--domain", "acme.com", "--web-search"],
    )
    assert result.exit_code == 0, result.output
    assert captured["body"] == {
        "icp_text": "VPs of Marketing",
        "domains": ["acme.com"],
        "web_search": True,
    }


def test_validate_icp_with_file_reads_domains_and_strips_blanks(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    domains_file = tmp_path / "domains.txt"
    domains_file.write_text("acme.com\n\n  beta.com  \n")
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"task_id": "vi-2"})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["validate-icp", "--icp", "VPs", "--file", str(domains_file)])
    assert result.exit_code == 0, result.output
    assert captured["body"] == {"icp_text": "VPs", "domains": ["acme.com", "beta.com"]}


def test_validate_icp_both_domain_and_file_exits_2(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    domains_file = tmp_path / "domains.txt"
    domains_file.write_text("acme.com\n")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"task_id": "vi-3"})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["validate-icp", "--icp", "VPs", "--domain", "acme.com", "--file", str(domains_file)])
    assert result.exit_code == 2


def test_validate_icp_neither_domain_nor_file_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"task_id": "vi-4"})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["validate-icp", "--icp", "VPs"])
    assert result.exit_code == 2


def test_validate_icp_with_wait_polls_to_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses = iter(
        [
            httpx.Response(200, json={"status": "processing", "progress": 20}),
            httpx.Response(200, json={"status": "completed", "progress": 100, "results": [{"domain": "acme.com"}]}),
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/validate/icp":
            return httpx.Response(200, json={"task_id": "vi-5"})
        assert request.url.path == "/v1/discogen/status/vi-5"
        return next(statuses)

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(
        app,
        ["validate-icp", "--icp", "VPs", "--domain", "acme.com", "--wait", "--timeout", "5"],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == [{"domain": "acme.com"}]
    assert "progress: 20%" in result.stderr


def test_append_json_response_emits_list(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    input_file = tmp_path / "domains.csv"
    input_file.write_text("domain\nacme.com\n")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/append"
        return httpx.Response(200, json=[{"domain": "acme.com"}])

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["append", str(input_file), "--dataset", "bizdata"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == [{"domain": "acme.com"}]


def test_append_csv_response_writes_output_file(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    input_file = tmp_path / "domains.csv"
    input_file.write_text("domain\nacme.com\n")
    output_file = tmp_path / "enriched.csv"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"domain,industry\nacme.com,SAAS\n", headers={"Content-Type": "text/csv"})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["append", str(input_file), "--csv", "--output", str(output_file)])
    assert result.exit_code == 0, result.output
    assert output_file.read_bytes() == b"domain,industry\nacme.com,SAAS\n"
    payload = json.loads(result.stdout)
    assert payload["written"] == str(output_file)
    assert payload["bytes"] == len(b"domain,industry\nacme.com,SAAS\n")


def test_append_csv_response_without_output_exits_2(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    input_file = tmp_path / "domains.csv"
    input_file.write_text("domain\nacme.com\n")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"domain\nacme.com\n", headers={"Content-Type": "text/csv"})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["append", str(input_file), "--csv"])
    assert result.exit_code == 2


def test_segment_with_domain_options_prints_task_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json={"task_id": "seg-1"})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["segment", "--domain", "acme.com", "--domain", "beta.com", "--max-segments", "3"])
    assert result.exit_code == 0, result.output
    request = captured["request"]
    assert request.url.path == "/v1/segment"
    assert request.url.params.get("domains") == "acme.com,beta.com"
    assert request.url.params.get("max_segments") == "3"
    payload = json.loads(result.stdout)
    assert payload["task_id"] == "seg-1"
    assert payload["task_family"] == "segment"


def test_segment_with_file_posts_upload(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    domains_file = tmp_path / "domains.csv"
    domains_file.write_text("domain\nacme.com\n")
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json={"task_id": "seg-2"})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["segment", "--file", str(domains_file)])
    assert result.exit_code == 0, result.output
    request = captured["request"]
    assert request.url.path == "/v1/segment"
    assert request.method == "POST"
    assert b"acme.com" in request.content


def test_segment_both_domain_and_file_exits_2(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    domains_file = tmp_path / "domains.csv"
    domains_file.write_text("domain\nacme.com\n")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"task_id": "seg-3"})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["segment", "--domain", "acme.com", "--file", str(domains_file)])
    assert result.exit_code == 2


def test_segment_neither_domain_nor_file_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"task_id": "seg-4"})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["segment"])
    assert result.exit_code == 2
