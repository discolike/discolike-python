from __future__ import annotations

import json
from collections.abc import Callable

import httpx2
from typer.testing import CliRunner

from discolike_cli.main import app
from discolike_testkit import Handler

runner = CliRunner()


def test_validate_icp_with_domain_options_posts_json(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx2.Response(200, json={"task_id": "vi-1"})

    install_build_client(handler)
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


def test_validate_icp_sends_web_search_when_passed(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["body"] = json.loads(request.content)
        return httpx2.Response(200, json={"task_id": "vi-1b"})

    install_build_client(handler)
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


def test_validate_icp_with_file_reads_domains_and_strips_blanks(
    tmp_path, install_build_client: Callable[[Handler], None]
) -> None:
    domains_file = tmp_path / "domains.txt"
    domains_file.write_text("acme.com\n\n  beta.com  \n")
    captured: dict[str, object] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["body"] = json.loads(request.content)
        return httpx2.Response(200, json={"task_id": "vi-2"})

    install_build_client(handler)
    result = runner.invoke(app, ["validate-icp", "--icp", "VPs", "--file", str(domains_file)])
    assert result.exit_code == 0, result.output
    assert captured["body"] == {"icp_text": "VPs", "domains": ["acme.com", "beta.com"]}


def test_validate_icp_both_domain_and_file_exits_2(tmp_path, install_build_client: Callable[[Handler], None]) -> None:
    domains_file = tmp_path / "domains.txt"
    domains_file.write_text("acme.com\n")

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"task_id": "vi-3"})

    install_build_client(handler)
    result = runner.invoke(app, ["validate-icp", "--icp", "VPs", "--domain", "acme.com", "--file", str(domains_file)])
    assert result.exit_code == 2


def test_validate_icp_neither_domain_nor_file_exits_2(install_build_client: Callable[[Handler], None]) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"task_id": "vi-4"})

    install_build_client(handler)
    result = runner.invoke(app, ["validate-icp", "--icp", "VPs"])
    assert result.exit_code == 2


def test_validate_icp_with_wait_polls_to_completion(install_build_client: Callable[[Handler], None]) -> None:
    statuses = iter(
        [
            httpx2.Response(200, json={"status": "processing", "progress": 20}),
            httpx2.Response(200, json={"status": "completed", "progress": 100, "results": [{"domain": "acme.com"}]}),
        ]
    )

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/v1/validate/icp":
            return httpx2.Response(200, json={"task_id": "vi-5"})
        assert request.url.path == "/v1/discogen/status/vi-5"
        return next(statuses)

    install_build_client(handler)
    result = runner.invoke(
        app,
        ["validate-icp", "--icp", "VPs", "--domain", "acme.com", "--wait", "--timeout", "5"],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == [{"domain": "acme.com"}]
    assert "progress: 20%" in result.stderr


def test_append_json_response_emits_list(tmp_path, install_build_client: Callable[[Handler], None]) -> None:
    input_file = tmp_path / "domains.csv"
    input_file.write_text("domain\nacme.com\n")

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/v1/append"
        return httpx2.Response(200, json=[{"domain": "acme.com"}])

    install_build_client(handler)
    result = runner.invoke(app, ["append", str(input_file), "--dataset", "bizdata"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == [{"domain": "acme.com"}]


def test_append_csv_response_writes_output_file(tmp_path, install_build_client: Callable[[Handler], None]) -> None:
    input_file = tmp_path / "domains.csv"
    input_file.write_text("domain\nacme.com\n")
    output_file = tmp_path / "enriched.csv"

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, content=b"domain,industry\nacme.com,SAAS\n", headers={"Content-Type": "text/csv"})

    install_build_client(handler)
    result = runner.invoke(app, ["append", str(input_file), "--csv", "--output", str(output_file)])
    assert result.exit_code == 0, result.output
    assert output_file.read_bytes() == b"domain,industry\nacme.com,SAAS\n"
    payload = json.loads(result.stdout)
    assert payload["written"] == str(output_file)
    assert payload["bytes"] == len(b"domain,industry\nacme.com,SAAS\n")


def test_append_csv_response_without_output_exits_2(tmp_path, install_build_client: Callable[[Handler], None]) -> None:
    input_file = tmp_path / "domains.csv"
    input_file.write_text("domain\nacme.com\n")

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, content=b"domain\nacme.com\n", headers={"Content-Type": "text/csv"})

    install_build_client(handler)
    result = runner.invoke(app, ["append", str(input_file), "--csv"])
    assert result.exit_code == 2


def test_segment_with_domain_options_prints_task_hint(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, httpx2.Request] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["request"] = request
        return httpx2.Response(200, json={"task_id": "seg-1"})

    install_build_client(handler)
    result = runner.invoke(app, ["segment", "--domain", "acme.com", "--domain", "beta.com", "--max-segments", "3"])
    assert result.exit_code == 0, result.output
    request = captured["request"]
    assert request.url.path == "/v1/segment"
    assert request.url.params.get("domains") == "acme.com,beta.com"
    assert request.url.params.get("max_segments") == "3"
    payload = json.loads(result.stdout)
    assert payload["task_id"] == "seg-1"
    assert payload["task_family"] == "segment"


def test_segment_with_file_posts_upload(tmp_path, install_build_client: Callable[[Handler], None]) -> None:
    domains_file = tmp_path / "domains.csv"
    domains_file.write_text("domain\nacme.com\n")
    captured: dict[str, httpx2.Request] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["request"] = request
        return httpx2.Response(200, json={"task_id": "seg-2"})

    install_build_client(handler)
    result = runner.invoke(app, ["segment", "--file", str(domains_file)])
    assert result.exit_code == 0, result.output
    request = captured["request"]
    assert request.url.path == "/v1/segment"
    assert request.method == "POST"
    assert b"acme.com" in request.content


def test_segment_both_domain_and_file_exits_2(tmp_path, install_build_client: Callable[[Handler], None]) -> None:
    domains_file = tmp_path / "domains.csv"
    domains_file.write_text("domain\nacme.com\n")

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"task_id": "seg-3"})

    install_build_client(handler)
    result = runner.invoke(app, ["segment", "--domain", "acme.com", "--file", str(domains_file)])
    assert result.exit_code == 2


def test_segment_neither_domain_nor_file_exits_2(install_build_client: Callable[[Handler], None]) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"task_id": "seg-4"})

    install_build_client(handler)
    result = runner.invoke(app, ["segment"])
    assert result.exit_code == 2
