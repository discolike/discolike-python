from __future__ import annotations

import json
from collections.abc import Callable

import httpx2
import pytest
from typer.testing import CliRunner

from discolike_cli.main import app
from discolike_testkit import Handler

runner = CliRunner()


def test_contacts_search_sends_options_and_param_escape_hatch(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, httpx2.QueryParams] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["params"] = request.url.params
        return httpx2.Response(200, json=[{"persona_id": 1, "domain": "acme.com"}])

    install_build_client(handler)
    result = runner.invoke(
        app,
        [
            "contacts",
            "search",
            "--icp-prompt",
            "VPs of Marketing",
            "--seniority",
            "vp",
            "--department",
            "Sales - Marketing",
            "--title",
            "VP Marketing",
            "--domain",
            "acme.com",
            "--person-country",
            "US",
            "--filter-industry",
            "SAAS",
            "--filter-country",
            "US",
            "--employee-range",
            "50-200",
            "--has-email",
            "--jobstart-date",
            "2025-01-01,2025-06-30",
            "--max-records",
            "20",
            "--offset",
            "5",
            "--param",
            "min_connections=5",
        ],
    )
    assert result.exit_code == 0, result.output
    params = captured["params"]
    assert params.get("icp_prompt") == "VPs of Marketing"
    assert params.get_list("seniority") == ["vp"]
    assert params.get_list("department") == ["Sales - Marketing"]
    assert params.get_list("title") == ["VP Marketing"]
    assert params.get_list("domain") == ["acme.com"]
    assert params.get_list("person_country") == ["US"]
    assert params.get_list("filter_industry") == ["SAAS"]
    assert params.get_list("filter_country") == ["US"]
    assert params.get("employee_range") == "50-200"
    assert params.get("has_email") == "true"
    assert params.get("jobstart_date") == "2025-01-01,2025-06-30"
    assert params.get("max_records") == "20"
    assert params.get("offset") == "5"
    assert params.get("min_connections") == "5"
    assert json.loads(result.stdout) == [
        {"persona_id": 1, "domain": "acme.com", "name": None, "title": None, "email": None}
    ]


def test_contacts_search_forwards_negate_options(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, httpx2.QueryParams] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["params"] = request.url.params
        return httpx2.Response(200, json=[])

    install_build_client(handler)
    result = runner.invoke(
        app,
        [
            "contacts",
            "search",
            "--negate-seniority",
            "entry_level",
            "--negate-department",
            "Human Resources",
            "--negate-title",
            "Assistant",
            "--negate-person-country",
            "FR",
            "--negate-filter-industry",
            "GAMING_AND_ESPORTS",
            "--negate-filter-country",
            "RU",
        ],
    )
    assert result.exit_code == 0, result.output
    params = captured["params"]
    assert params.get_list("negate_seniority") == ["entry_level"]
    assert params.get_list("negate_department") == ["Human Resources"]
    assert params.get_list("negate_title") == ["Assistant"]
    assert params.get_list("negate_person_country") == ["FR"]
    assert params.get_list("negate_filter_industry") == ["GAMING_AND_ESPORTS"]
    assert params.get_list("negate_filter_country") == ["RU"]


def test_contacts_search_icp_text_is_removed(install_build_client: Callable[[Handler], None]) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json=[])

    install_build_client(handler)
    result = runner.invoke(app, ["contacts", "search", "--icp-text", "X"])
    assert result.exit_code == 2


def test_contacts_search_unknown_param_passes_through(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, httpx2.QueryParams] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["params"] = request.url.params
        return httpx2.Response(200, json=[])

    install_build_client(handler)
    result = runner.invoke(app, ["contacts", "search", "--param", "bogus_kwarg=1"])
    assert result.exit_code == 0, result.output
    assert captured["params"].get("bogus_kwarg") == "1"


def test_contacts_search_invalid_seniority_exits_2(install_build_client: Callable[[Handler], None]) -> None:
    install_build_client(lambda request: httpx2.Response(200, json=[]))
    result = runner.invoke(app, ["contacts", "search", "--seniority", "intern"])
    assert result.exit_code == 2
    payload = json.loads(result.stderr)
    assert payload["error"] == "ValidationError"
    assert "seniority" in payload["message"]


def test_contacts_search_unauthorized_exits_3(install_build_client: Callable[[Handler], None]) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(401, json={"detail": "invalid key"})

    install_build_client(handler)
    result = runner.invoke(app, ["contacts", "search", "--icp-prompt", "X"])
    assert result.exit_code == 3
    payload = json.loads(result.stderr)
    assert payload["error"] == "AuthenticationError"


def test_contacts_count_sends_shared_subset(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, httpx2.QueryParams] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["params"] = request.url.params
        return httpx2.Response(200, json={"count": 12})

    install_build_client(handler)
    result = runner.invoke(app, ["contacts", "count", "--seniority", "vp", "--param", "min_connections=5"])
    assert result.exit_code == 0, result.output
    request_path = captured["params"]
    assert request_path.get_list("seniority") == ["vp"]
    assert request_path.get("min_connections") == "5"
    assert "max_records" not in request_path
    assert json.loads(result.stdout) == {"count": 12}


def test_contacts_lookup_by_persona_id(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, httpx2.Request] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["request"] = request
        return httpx2.Response(200, json={"persona_id": 7, "domain": "acme.com"})

    install_build_client(handler)
    result = runner.invoke(app, ["contacts", "lookup", "--persona-id", "7", "--email", "jane@acme.com"])
    assert result.exit_code == 0, result.output
    request = captured["request"]
    assert request.url.path == "/v1/contacts/lookup"
    assert request.url.params.get("persona_id") == "7"
    assert request.url.params.get("email") == "jane@acme.com"
    assert json.loads(result.stdout) == {
        "persona_id": 7,
        "domain": "acme.com",
        "name": None,
        "title": None,
        "email": None,
    }


def test_contacts_match_hits_match_endpoint(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, httpx2.Request] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["request"] = request
        return httpx2.Response(200, json={"matches": []})

    install_build_client(handler)
    result = runner.invoke(
        app,
        ["contacts", "match", "Jane Doe", "--company-name", "Acme Corp", "--domain", "acme.com", "--limit", "5"],
    )
    assert result.exit_code == 0, result.output
    request = captured["request"]
    assert request.url.path == "/v1/contacts/match"
    assert request.url.params.get("name") == "Jane Doe"
    assert request.url.params.get("company_name") == "Acme Corp"
    assert request.url.params.get("domain") == "acme.com"
    assert request.url.params.get("limit") == "5"


def test_contacts_bulk_match_without_wait_prints_task_hint(
    tmp_path, install_build_client: Callable[[Handler], None]
) -> None:
    queries_file = tmp_path / "queries.json"
    queries_file.write_text(json.dumps([{"name": "Jane Doe"}]))
    captured: dict[str, httpx2.Request] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["request"] = request
        return httpx2.Response(200, json={"task_id": "cm-1"})

    install_build_client(handler)
    result = runner.invoke(app, ["contacts", "bulk-match", "--queries-file", str(queries_file)])
    assert result.exit_code == 0, result.output
    request = captured["request"]
    assert request.url.path == "/v1/contacts/bulk-match"
    body = json.loads(request.content)
    assert body["queries"] == [{"name": "Jane Doe"}]
    payload = json.loads(result.stdout)
    assert payload["task_id"] == "cm-1"
    assert payload["task_family"] == "contactmatch"


@pytest.mark.parametrize("content", ["not json", "{}"])
def test_contacts_bulk_match_bad_queries_file_exits_2(
    tmp_path, content: str, install_build_client: Callable[[Handler], None]
) -> None:
    queries_file = tmp_path / "queries.json"
    queries_file.write_text(content)

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"task_id": "cm-1"})

    install_build_client(handler)
    result = runner.invoke(app, ["contacts", "bulk-match", "--queries-file", str(queries_file)])
    assert result.exit_code == 2


def test_contacts_bulk_match_with_wait_polls_to_completion(
    tmp_path, install_build_client: Callable[[Handler], None]
) -> None:
    queries_file = tmp_path / "queries.json"
    queries_file.write_text(json.dumps([{"name": "Jane Doe"}]))
    statuses = iter(
        [
            httpx2.Response(200, json={"status": "processing", "progress": 30}),
            httpx2.Response(200, json={"status": "completed", "progress": 100, "results": [{"persona_id": 1}]}),
        ]
    )

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/v1/contacts/bulk-match":
            return httpx2.Response(200, json={"task_id": "cm-2"})
        assert request.url.path == "/v1/contactmatch/status/cm-2"
        return next(statuses)

    install_build_client(handler)
    result = runner.invoke(
        app,
        ["contacts", "bulk-match", "--queries-file", str(queries_file), "--wait", "--timeout", "5"],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == [{"persona_id": 1}]
    assert "progress: 30%" in result.stderr


def test_contacts_discover_posts_json_body(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx2.Response(200, json={"results": {}, "total_contacts": 0})

    install_build_client(handler)
    result = runner.invoke(
        app,
        [
            "contacts",
            "discover",
            "--domain",
            "acme.com",
            "--results-by-company",
            "10",
            "--include-search-contacts",
            "--consensus",
            "2",
        ],
    )
    assert result.exit_code == 0, result.output
    assert captured["path"] == "/v1/contacts/discover"
    assert captured["body"] == {
        "domain": ["acme.com"],
        "results_by_company": 10,
        "include_search_contacts": True,
        "consensus": 2,
    }


def test_contacts_generate_without_wait_prints_task_hint(install_build_client: Callable[[Handler], None]) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx2.Response(200, json={"task_id": "dg-1"})

    install_build_client(handler)
    result = runner.invoke(
        app,
        [
            "contacts",
            "generate",
            "--icp-text",
            "VPs of Marketing",
            "--domain",
            "acme.com",
            "--domain",
            "beta.com",
        ],
    )
    assert result.exit_code == 0, result.output
    assert captured["path"] == "/v1/contacts/discover/generate"
    assert captured["body"] == {
        "icp_text": "VPs of Marketing",
        "domains": ["acme.com", "beta.com"],
    }
    payload = json.loads(result.stdout)
    assert payload["task_id"] == "dg-1"
    assert payload["task_family"] == "discogen"
