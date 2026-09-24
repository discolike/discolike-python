"""discolike bulk companies|estimate|contacts (issue #24) — the pipeline mechanics, driven through a mock transport."""

from __future__ import annotations

import csv
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2
import pytest
from typer.testing import CliRunner

from discolike_cli import bulk
from discolike_cli.main import app
from discolike_testkit import Handler
from discolike_testkit import plain_output

runner = CliRunner()
NO_LIMIT = ["--rate-limit", "1000000"]


def _companies(prefix: str, count: int) -> list[dict[str, Any]]:
    return [
        {"domain": f"{prefix}{i}.com", "name": f"{prefix.upper()} {i}", "employees": "11-50", "similarity": 0.9}
        for i in range(count)
    ]


def _fingerprint(domains: list[str], per_company: int) -> str:
    """The checkpoint stamp for a contacts pull with only the default filters."""
    filters = bulk._contact_filters(
        None,
        None,
        icp_prompt=None,
        summary=None,
        negate_summary=None,
        seniority=None,
        negate_seniority=None,
        department=None,
        negate_department=None,
        title=None,
        negate_title=None,
        person_country=None,
        person_state=None,
        has_email=True,
        exclusion_query_id=None,
    )
    return f"fingerprint={bulk._checkpoint_fingerprint(domains, per_company, filters)}"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


class Recorder:
    """Records every request and answers from a per-path queue of responses."""

    def __init__(self, **queues: list[Any]) -> None:
        self.queues = queues
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        key = request.url.path.removeprefix("/v1/").replace("/", "_").replace("-", "_")
        queue = self.queues[key]
        payload = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(payload, int):
            return httpx2.Response(payload, json={"detail": "nope"})
        return httpx2.Response(200, json=payload)

    def bodies(self, path: str) -> list[dict[str, Any]]:
        return [json.loads(r.content) for r in self.requests if r.url.path == path]

    def params(self, path: str) -> list[httpx2.QueryParams]:
        return [r.url.params for r in self.requests if r.url.path == path]


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _seconds: None)


# --------------------------------------------------------------------------- companies


def test_bulk_companies_pages_with_exclusion_lists_and_appends_csv(
    install_build_client: Callable[[Handler], None], tmp_path: Path
) -> None:
    recorder = Recorder(
        discover=[_companies("a", 20), _companies("b", 5)],
        queries_exclusion_list=[{"query_id": "q-round-1"}],
    )
    install_build_client(recorder)
    out = tmp_path / "companies.csv"
    result = runner.invoke(
        app,
        [
            "bulk",
            "companies",
            "--icp-prompt",
            "agencies",
            "--page-size",
            "20",
            "--max-companies",
            "100",
            "--run-name",
            "agencies",
            "--out",
            str(out),
            *NO_LIMIT,
        ],
    )
    assert result.exit_code == 0, result.output

    discover = recorder.params("/v1/discover")
    assert [p.get("max_records") for p in discover] == ["20", "20"]
    assert discover[0].get("exclusion_query_id") is None
    assert discover[1].get_list("exclusion_query_id") == ["q-round-1"]
    assert recorder.bodies("/v1/queries/exclusion-list") == [
        {"query_name": "agencies-round-1", "domains": [f"a{i}.com" for i in range(20)]}
    ]

    rows = _read_csv(out)
    assert len(rows) == 25
    assert rows[0] == {"domain": "a0.com", "name": "A 0", "country": "", "employees": "11-50", "similarity": "0.9"}

    summary = json.loads(result.stdout)
    assert summary["companies"] == 25
    assert summary["rounds"] == 2
    assert summary["exclusion_query_ids"] == ["q-round-1"]
    assert summary["out"] == str(out)


def test_bulk_companies_short_tail_rides_inline_exclude_domain(
    install_build_client: Callable[[Handler], None], tmp_path: Path
) -> None:
    page_one = _companies("a", 20)
    page_two = [*_companies("a", 5), *_companies("b", 15)]  # 5 already seen, 15 net-new (< 20, no saved list)
    recorder = Recorder(
        discover=[page_one, page_two, []],
        queries_exclusion_list=[{"query_id": "q1"}],
    )
    install_build_client(recorder)
    result = runner.invoke(
        app,
        [
            "bulk",
            "companies",
            "--icp-prompt",
            "x",
            "--page-size",
            "20",
            "--max-companies",
            "100",
            "--out",
            str(tmp_path / "c.csv"),
            *NO_LIMIT,
        ],
    )
    assert result.exit_code == 0, result.output
    assert len(recorder.bodies("/v1/queries/exclusion-list")) == 1
    third = recorder.params("/v1/discover")[2]
    assert third.get_list("exclusion_query_id") == ["q1"]
    assert third.get_list("exclude_domain") == [f"b{i}.com" for i in range(15)]
    assert len(_read_csv(tmp_path / "c.csv")) == 35


def test_bulk_companies_stops_at_max_companies(install_build_client: Callable[[Handler], None], tmp_path: Path) -> None:
    recorder = Recorder(
        discover=[_companies("a", 20), _companies("b", 20)], queries_exclusion_list=[{"query_id": "q1"}]
    )
    install_build_client(recorder)
    result = runner.invoke(
        app,
        [
            "bulk",
            "companies",
            "--icp-prompt",
            "x",
            "--page-size",
            "20",
            "--max-companies",
            "40",
            "--out",
            str(tmp_path / "c.csv"),
            *NO_LIMIT,
        ],
    )
    assert result.exit_code == 0, result.output
    assert len(recorder.params("/v1/discover")) == 2
    assert len(_read_csv(tmp_path / "c.csv")) == 40


def test_bulk_companies_resumes_from_existing_csv(
    install_build_client: Callable[[Handler], None], tmp_path: Path
) -> None:
    out = tmp_path / "companies.csv"
    out.write_text("domain,name,country,employees,similarity\n" + "".join(f"old{i}.com,,,,\n" for i in range(25)))
    recorder = Recorder(discover=[_companies("n", 3)], queries_exclusion_list=[{"query_id": "q-resume"}])
    install_build_client(recorder)
    result = runner.invoke(
        app,
        [
            "bulk",
            "companies",
            "--icp-prompt",
            "x",
            "--page-size",
            "20",
            "--max-companies",
            "100",
            "--run-name",
            "r",
            "--out",
            str(out),
            *NO_LIMIT,
        ],
    )
    assert result.exit_code == 0, result.output
    assert recorder.bodies("/v1/queries/exclusion-list") == [
        {"query_name": "r-resume-0", "domains": [f"old{i}.com" for i in range(25)]}
    ]
    assert recorder.params("/v1/discover")[0].get_list("exclusion_query_id") == ["q-resume"]
    assert len(_read_csv(out)) == 28
    summary = json.loads(result.stdout)
    assert summary == {**summary, "companies": 28, "new": 3}


def test_bulk_companies_resume_still_excludes_the_csv_when_a_suppression_list_is_supplied(
    install_build_client: Callable[[Handler], None], tmp_path: Path
) -> None:
    out = tmp_path / "companies.csv"
    out.write_text("domain,name,country,employees,similarity\n" + "".join(f"old{i}.com,,,,\n" for i in range(25)))
    recorder = Recorder(discover=[_companies("n", 3)], queries_exclusion_list=[{"query_id": "q-resume"}])
    install_build_client(recorder)
    result = runner.invoke(
        app,
        [
            "bulk",
            "companies",
            "--icp-prompt",
            "x",
            "--page-size",
            "20",
            "--max-companies",
            "100",
            "--run-name",
            "r",
            "--exclusion-query-id",
            "q-customers",
            "--out",
            str(out),
            *NO_LIMIT,
        ],
    )
    assert result.exit_code == 0, result.output
    assert recorder.bodies("/v1/queries/exclusion-list") == [
        {"query_name": "r-resume-0", "domains": [f"old{i}.com" for i in range(25)]}
    ]
    assert recorder.params("/v1/discover")[0].get_list("exclusion_query_id") == ["q-customers", "q-resume"]


def test_bulk_companies_overwrite_ignores_existing_csv(
    install_build_client: Callable[[Handler], None], tmp_path: Path
) -> None:
    out = tmp_path / "companies.csv"
    out.write_text("domain,name,country,employees,similarity\nold.com,,,,\n")
    recorder = Recorder(discover=[_companies("n", 3)], queries_exclusion_list=[{"query_id": "q"}])
    install_build_client(recorder)
    result = runner.invoke(app, ["bulk", "companies", "--icp-prompt", "x", "--overwrite", "--out", str(out), *NO_LIMIT])
    assert result.exit_code == 0, result.output
    assert recorder.bodies("/v1/queries/exclusion-list") == []
    assert [row["domain"] for row in _read_csv(out)] == ["n0.com", "n1.com", "n2.com"]


def test_bulk_companies_takes_params_file_and_drops_managed_keys(
    install_build_client: Callable[[Handler], None], tmp_path: Path
) -> None:
    form = tmp_path / "form.json"
    form.write_text(json.dumps({"country": ["US"], "variance": "MID_HIGH", "max_records": 5, "offset": 99}))
    recorder = Recorder(discover=[[]], queries_exclusion_list=[{"query_id": "q"}])
    install_build_client(recorder)
    result = runner.invoke(
        app,
        [
            "bulk",
            "companies",
            "--params-file",
            str(form),
            "--param",
            "consensus=3",
            "--variance",
            "LOW",
            "--out",
            str(tmp_path / "c.csv"),
            *NO_LIMIT,
        ],
    )
    assert result.exit_code == 0, result.output
    params = recorder.params("/v1/discover")[0]
    assert params.get_list("country") == ["US"]
    assert params.get("variance") == "LOW"
    assert params.get("consensus") == "3"
    assert params.get("max_records") == "10000"
    assert params.get("offset") is None
    assert "max_records" in result.output
    assert "managed by bulk" in result.output


def test_bulk_companies_validates_before_first_call(
    install_build_client: Callable[[Handler], None], tmp_path: Path
) -> None:
    recorder = Recorder(discover=[[]])
    install_build_client(recorder)
    result = runner.invoke(
        app, ["bulk", "companies", "--variance", "BOGUS", "--out", str(tmp_path / "c.csv"), *NO_LIMIT]
    )
    assert result.exit_code == 2
    assert "ValidationError" in result.output
    assert recorder.requests == []


def test_bulk_companies_retries_after_rate_limit(
    install_build_client: Callable[[Handler], None], tmp_path: Path
) -> None:
    # The SDK transport retries a 429 three times on its own; bulk retries the surfaced RateLimitError again.
    recorder = Recorder(discover=[429, 429, 429, 429, _companies("a", 2)])
    install_build_client(recorder)
    result = runner.invoke(app, ["bulk", "companies", "--icp-prompt", "x", "--out", str(tmp_path / "c.csv"), *NO_LIMIT])
    assert result.exit_code == 0, result.output
    assert len(recorder.params("/v1/discover")) == 5
    assert len(_read_csv(tmp_path / "c.csv")) == 2


# --------------------------------------------------------------------------- estimate


def test_bulk_estimate_counts_per_slice_and_caps(
    install_build_client: Callable[[Handler], None], tmp_path: Path
) -> None:
    domains = tmp_path / "companies.csv"
    domains.write_text("domain\n" + "".join(f"d{i}.com\n" for i in range(2500)))
    recorder = Recorder(contacts_count=[{"count": 30000}, {"count": 30000}, {"count": 1000}])
    install_build_client(recorder)
    result = runner.invoke(
        app,
        ["bulk", "estimate", "--domains-file", str(domains), "--per-company", "10", "--seniority", "vp", *NO_LIMIT],
    )
    assert result.exit_code == 0, result.output
    calls = recorder.params("/v1/contacts/count")
    assert [len(p.get_list("domain")) for p in calls] == [1000, 1000, 500]
    assert calls[0].get_list("seniority") == ["vp"]
    assert calls[0].get("has_email") == "true"
    assert calls[0].get("max_records") is None
    summary = json.loads(result.stdout)
    assert summary == {"companies": 2500, "contacts_available": 61000, "contacts_capped": 25000, "per_company": 10}


# --------------------------------------------------------------------------- contacts


def _discover_payload(domains: list[str], per: int, start: int = 0) -> dict[str, Any]:
    results = {}
    for d_index, domain in enumerate(domains):
        results[domain] = {
            "domain": domain,
            "name": domain.upper(),
            "contacts": [
                {
                    "persona_id": start + d_index * per + c,
                    "name": f"First{c} Last{c}",
                    "title": "VP",
                    "email": f"p{c}@{domain}",
                    "phone": [{"phone": "+1"}],
                    "social_urls": [f"https://linkedin.com/in/p{c}"],
                    "industry": ["ACCOUNTING", "LEGAL"],
                }
                for c in range(per)
            ],
        }
    return {"results": results}


def test_bulk_contacts_slices_domains_and_flattens_rows(
    install_build_client: Callable[[Handler], None], tmp_path: Path
) -> None:
    all_domains = [f"d{i}.com" for i in range(250)]
    domains = tmp_path / "companies.csv"
    domains.write_text("domain\n" + "".join(f"{d}\n" for d in all_domains))
    # per-company 100 => 10000 // 100 = 100 domains per call => slices of 100, 100, 50
    recorder = Recorder(
        contacts_discover=[
            _discover_payload(all_domains[:2], 2, start=0),
            _discover_payload(all_domains[100:102], 2, start=100),
            _discover_payload(all_domains[200:201], 2, start=200),
        ]
    )
    install_build_client(recorder)
    out = tmp_path / "contacts.csv"
    result = runner.invoke(
        app,
        [
            "bulk",
            "contacts",
            "--domains-file",
            str(domains),
            "--per-company",
            "100",
            "--summary",
            "growth",
            "--negate-summary",
            "bookkeeping",
            "--out",
            str(out),
            *NO_LIMIT,
        ],
    )
    assert result.exit_code == 0, result.output
    bodies = recorder.bodies("/v1/contacts/discover")
    assert [b["domain"] for b in bodies] == [all_domains[:100], all_domains[100:200], all_domains[200:]]
    assert bodies[0]["results_by_company"] == 100
    assert bodies[0]["max_records"] == 10000
    assert bodies[2]["max_records"] == 5000
    assert bodies[0]["summary"] == "growth"
    stamp, *indexes = (tmp_path / "contacts.csv.checkpoint").read_text().split()
    assert stamp.startswith("fingerprint=")
    assert indexes == ["0", "1", "2"]
    assert bodies[0]["negate_summary"] == "bookkeeping"
    assert bodies[0]["has_email"] is True
    assert "offset" not in bodies[0]

    rows = _read_csv(out)
    assert len(rows) == 10
    assert rows[0]["persona_id"] == "0"
    assert rows[0]["first_name"] == "First0"
    assert rows[0]["last_name"] == "Last0"
    assert rows[0]["email"] == "p0@d0.com"
    assert rows[0]["phone"] == "+1"
    assert rows[0]["linkedin"] == "https://linkedin.com/in/p0"
    assert rows[0]["industry"] == "ACCOUNTING;LEGAL"
    assert rows[0]["domain"] == "d0.com"
    assert rows[0]["company_name"] == "D0.COM"

    summary = json.loads(result.stdout)
    assert summary["companies"] == 250
    assert summary["slices"] == 3
    assert summary["contacts"] == 10
    assert summary["out"] == str(out)


def test_bulk_contacts_resume_skips_checkpointed_slices(
    install_build_client: Callable[[Handler], None], tmp_path: Path
) -> None:
    all_domains = [f"d{i}.com" for i in range(250)]
    domains = tmp_path / "companies.csv"
    domains.write_text("domain\n" + "".join(f"{d}\n" for d in all_domains))
    out = tmp_path / "contacts.csv"
    out.write_text("persona_id,domain\n1,a.com\n")
    (tmp_path / "contacts.csv.checkpoint").write_text(f"{_fingerprint(all_domains, 100)}\n0\n1\n")
    recorder = Recorder(contacts_discover=[_discover_payload(all_domains[200:201], 1, start=200)])
    install_build_client(recorder)
    result = runner.invoke(
        app,
        ["bulk", "contacts", "--domains-file", str(domains), "--per-company", "100", "--out", str(out), *NO_LIMIT],
    )
    assert result.exit_code == 0, result.output
    assert [b["domain"] for b in recorder.bodies("/v1/contacts/discover")] == [all_domains[200:]]
    assert (tmp_path / "contacts.csv.checkpoint").read_text().split() == [_fingerprint(all_domains, 100), "0", "1", "2"]
    assert out.read_text().splitlines()[1] == "1,a.com"  # existing rows kept, header not repeated
    summary = json.loads(result.stdout)
    assert summary["slices_run"] == 1


def test_bulk_contacts_overwrite_clears_checkpoint(
    install_build_client: Callable[[Handler], None], tmp_path: Path
) -> None:
    domains = tmp_path / "companies.csv"
    domains.write_text("domain\na.com\n")
    out = tmp_path / "contacts.csv"
    out.write_text("stale\n")
    (tmp_path / "contacts.csv.checkpoint").write_text("0\n")
    recorder = Recorder(contacts_discover=[_discover_payload(["a.com"], 1)])
    install_build_client(recorder)
    result = runner.invoke(
        app, ["bulk", "contacts", "--domains-file", str(domains), "--overwrite", "--out", str(out), *NO_LIMIT]
    )
    assert result.exit_code == 0, result.output
    assert len(recorder.bodies("/v1/contacts/discover")) == 1
    assert len(_read_csv(out)) == 1


def test_bulk_contacts_dedupes_persona_ids_within_run(
    install_build_client: Callable[[Handler], None], tmp_path: Path
) -> None:
    domains = tmp_path / "companies.csv"
    domains.write_text("domain\na.com\nb.com\n")
    recorder = Recorder(contacts_discover=[_discover_payload(["a.com", "b.com"], 2, start=0)])
    install_build_client(recorder)
    result = runner.invoke(
        app, ["bulk", "contacts", "--domains-file", str(domains), "--out", str(tmp_path / "c.csv"), *NO_LIMIT]
    )
    assert result.exit_code == 0, result.output
    assert len(_read_csv(tmp_path / "c.csv")) == 4


def test_bulk_contacts_drops_managed_keys_from_params_file(
    install_build_client: Callable[[Handler], None], tmp_path: Path
) -> None:
    domains = tmp_path / "companies.csv"
    domains.write_text("domain\na.com\n")
    form = tmp_path / "form.json"
    form.write_text(json.dumps({"domain": ["z.com"], "results_by_company": 1, "offset": 5, "seniority": ["vp"]}))
    recorder = Recorder(contacts_discover=[_discover_payload(["a.com"], 1)])
    install_build_client(recorder)
    result = runner.invoke(
        app,
        [
            "bulk",
            "contacts",
            "--domains-file",
            str(domains),
            "--params-file",
            str(form),
            "--per-company",
            "3",
            "--out",
            str(tmp_path / "c.csv"),
            *NO_LIMIT,
        ],
    )
    assert result.exit_code == 0, result.output
    body = recorder.bodies("/v1/contacts/discover")[0]
    assert body["domain"] == ["a.com"]
    assert body["results_by_company"] == 3
    assert "offset" not in body
    assert body["seniority"] == ["vp"]
    assert "managed by bulk" in result.output


def test_bulk_companies_trims_last_page_to_max_companies(
    install_build_client: Callable[[Handler], None], tmp_path: Path
) -> None:
    # The API floor is 20 per call, so the final page can return more than the run still needs.
    recorder = Recorder(discover=[_companies("a", 20), _companies("b", 20)], queries_exclusion_list=[{"query_id": "q"}])
    install_build_client(recorder)
    result = runner.invoke(
        app,
        ["bulk", "companies", "--icp-prompt", "x", "--page-size", "20", "--max-companies", "30",
         "--out", str(tmp_path / "c.csv"), *NO_LIMIT],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert len(_read_csv(tmp_path / "c.csv")) == 30
    assert json.loads(result.stdout)["companies"] == 30


def test_bulk_contacts_resume_dedupes_against_rows_already_in_csv(
    install_build_client: Callable[[Handler], None], tmp_path: Path
) -> None:
    domains = tmp_path / "companies.csv"
    domains.write_text("domain\na.com\n")
    out = tmp_path / "contacts.csv"
    out.write_text("persona_id,domain\n0,a.com\n")  # a lost checkpoint reruns slice 0
    recorder = Recorder(contacts_discover=[_discover_payload(["a.com"], 2)])
    install_build_client(recorder)
    result = runner.invoke(app, ["bulk", "contacts", "--domains-file", str(domains), "--out", str(out), *NO_LIMIT])
    assert result.exit_code == 0, result.output
    assert [row["persona_id"] for row in _read_csv(out)] == ["0", "1"]


def test_bulk_contacts_refuses_checkpoint_written_for_other_inputs(
    install_build_client: Callable[[Handler], None], tmp_path: Path
) -> None:
    domains = tmp_path / "companies.csv"
    domains.write_text("domain\na.com\nb.com\n")
    out = tmp_path / "contacts.csv"
    out.write_text("persona_id,domain\n0,a.com\n")
    (tmp_path / "contacts.csv.checkpoint").write_text(f"{_fingerprint(['a.com'], 100)}\n0\n")  # b.com added since
    recorder = Recorder(contacts_discover=[_discover_payload(["a.com", "b.com"], 1)])
    install_build_client(recorder)
    result = runner.invoke(app, ["bulk", "contacts", "--domains-file", str(domains), "--out", str(out), *NO_LIMIT])
    assert result.exit_code == 2, result.output
    assert "written for a different domains file" in plain_output(result.output)
    assert recorder.requests == []  # nothing billed, nothing skipped
    # --per-company changes the slicing, so the same domains still refuse to resume
    (tmp_path / "contacts.csv.checkpoint").write_text(f"{_fingerprint(['a.com', 'b.com'], 50)}\n0\n")
    result = runner.invoke(app, ["bulk", "contacts", "--domains-file", str(domains), "--out", str(out), *NO_LIMIT])
    assert result.exit_code == 2, result.output
    # --overwrite discards it
    result = runner.invoke(
        app, ["bulk", "contacts", "--domains-file", str(domains), "--out", str(out), "--overwrite", *NO_LIMIT]
    )
    assert result.exit_code == 0, result.output
    assert len(_read_csv(out)) == 2


def test_bulk_contacts_writes_every_contact_without_persona_id(
    install_build_client: Callable[[Handler], None], tmp_path: Path
) -> None:
    domains = tmp_path / "companies.csv"
    domains.write_text("domain\na.com\n")
    payload = _discover_payload(["a.com"], 3)
    for contact in payload["results"]["a.com"]["contacts"]:
        contact["persona_id"] = None
    recorder = Recorder(contacts_discover=[payload])
    install_build_client(recorder)
    result = runner.invoke(
        app, ["bulk", "contacts", "--domains-file", str(domains), "--out", str(tmp_path / "c.csv"), *NO_LIMIT]
    )
    assert result.exit_code == 0, result.output
    assert [row["email"] for row in _read_csv(tmp_path / "c.csv")] == ["p0@a.com", "p1@a.com", "p2@a.com"]


def test_bulk_companies_consolidates_inline_tails_into_a_saved_list(
    install_build_client: Callable[[Handler], None], tmp_path: Path
) -> None:
    # Every page is 20 companies of which only 10 are net-new: each tail is too short for a saved list on
    # its own, so tails ride on exclude_domain until two of them together reach the 20-domain minimum.
    pages = [
        _companies("a", 20),
        [*_companies("a", 10), *_companies("b", 10)],
        [*_companies("b", 10), *_companies("c", 10)],
        [*_companies("c", 10), *_companies("d", 10)],
        [],
    ]
    recorder = Recorder(discover=pages, queries_exclusion_list=[{"query_id": "q1"}, {"query_id": "q2"}])
    install_build_client(recorder)
    result = runner.invoke(
        app,
        ["bulk", "companies", "--icp-prompt", "x", "--page-size", "20", "--out", str(tmp_path / "c.csv"), *NO_LIMIT],
    )
    assert result.exit_code == 0, result.output
    lists = recorder.bodies("/v1/queries/exclusion-list")
    assert [sorted(body["domains"]) for body in lists] == [
        sorted(c["domain"] for c in _companies("a", 20)),
        sorted(c["domain"] for c in [*_companies("b", 10), *_companies("c", 10)]),
    ]
    assert lists[1]["query_name"] == "bulk-round-3-tails"
    calls = recorder.params("/v1/discover")
    assert calls[2].get_list("exclude_domain") == [c["domain"] for c in _companies("b", 10)]
    assert calls[3].get_list("exclusion_query_id") == ["q1", "q2"]
    assert calls[3].get_list("exclude_domain") == []  # consolidated, nothing inline
    assert calls[4].get_list("exclude_domain") == [c["domain"] for c in _companies("d", 10)]
    assert len(_read_csv(tmp_path / "c.csv")) == 50


@pytest.mark.parametrize("command", [["companies", "--icp-prompt", "x"], ["estimate"], ["contacts"]])
def test_bulk_rejects_non_positive_rate_limit(
    install_build_client: Callable[[Handler], None], tmp_path: Path, command: list[str]
) -> None:
    domains = tmp_path / "companies.csv"
    domains.write_text("domain\na.com\n")
    recorder = Recorder()
    install_build_client(recorder)
    extra = [] if command[0] == "companies" else ["--domains-file", str(domains)]
    result = runner.invoke(app, ["bulk", *command, *extra, "--out", str(tmp_path / "c.csv"), "--rate-limit", "0"])
    assert result.exit_code == 2, result.output
    assert recorder.requests == []
