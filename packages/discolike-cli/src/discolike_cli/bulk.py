"""``discolike bulk``: the volume pipeline — companies past 10k, contacts by domain slice, checkpoint and resume.

Ports the mechanics of the support-side ``discolike_pipeline.py`` so an agent can drive the whole
flow with plain ``discolike`` calls (see issue #24). Progress goes to stderr, a JSON summary to stdout.
"""

from __future__ import annotations

import csv
import functools
import pathlib
import sys
import time
from collections import deque
from collections.abc import Callable
from collections.abc import Iterator
from typing import Any
from typing import TypeVar

import pydantic
import typer

from discolike import Discolike
from discolike._exceptions import AuthenticationError
from discolike._exceptions import DiscolikeError
from discolike._exceptions import NotFoundError
from discolike._exceptions import PlanAccessError
from discolike._exceptions import RateLimitError
from discolike._exceptions import ValidationError
from discolike.requests import ContactFilters
from discolike.requests import ContactsCountParams
from discolike.requests import CreateExclusionListRequest
from discolike.requests import DiscoverParams
from discolike_cli._inputs import read_domains_file
from discolike_cli._output import build_request
from discolike_cli._output import emit
from discolike_cli._output import handle_errors
from discolike_cli.discover import DOMAINS_FILE_HELP
from discolike_cli.discover import PARAM_HELP
from discolike_cli.discover import PARAMS_FILE_HELP
from discolike_cli.discover import _merge_params

T = TypeVar("T")

MAX_RECORDS = 10000  # API ceiling per discover / contacts call
MIN_RECORDS = 20  # API floor on max_records
MAX_PER_COMPANY = 100  # API ceiling on results_by_company
MIN_EXCLUSION_LIST = 20  # saved lists reject anything smaller; shorter tails ride on exclude_domain
EXCLUSION_CAPACITY = 250_000  # domains an account can hold across exclusion lists (every plan)
COUNT_SLICE = 1000  # domains per free /contacts/count probe
RETRY_ATTEMPTS = 5
RETRY_BASE_SECONDS = 5.0
RETRY_MAX_SECONDS = 60.0
CLIENT_TIMEOUT_SECONDS = 300.0
DEFAULT_RATE_LIMIT_PER_MINUTE = 10  # Pro on /discover and /contacts; Starter 5, Team 15, Company 25, Enterprise 50
COUNT_RATE_LIMIT_PER_MINUTE = 30

COMPANY_COLUMNS = ["domain", "name", "country", "employees", "similarity"]
CONTACT_COLUMNS = [
    "persona_id", "first_name", "last_name", "name", "title", "seniority", "department",
    "email", "email_validated", "phone", "linkedin", "connections",
    "domain", "company_name", "country", "state", "industry", "employees", "revenue_range", "jobstart_date",
]  # fmt: skip
COMPANIES_MANAGED = ("exclusion_query_id", "exclude_domain", "max_records", "offset")
CONTACTS_MANAGED = ("domain", "max_records", "offset", "results_by_company", "max_companies")
FATAL = (ValidationError, AuthenticationError, PlanAccessError, NotFoundError, pydantic.ValidationError)

RATE_LIMIT_HELP = "Calls per minute to stay under for the paid endpoint (Pro is 10 on /discover and /contacts)."
OVERWRITE_HELP = "Ignore an existing --out (and checkpoint) and start clean instead of resuming."
PER_COMPANY_HELP = "Contacts to pull per company (sets results_by_company and the domain slice size)."
EXCLUSION_QUERY_ID_HELP = "Saved query ID whose results are excluded (repeatable)."

app = typer.Typer(
    help=(
        "Volume pulls with checkpoint and resume: walk the company index past the 10,000-per-search ceiling, "
        "size a contact pull for free, then pull N contacts per company into one CSV."
    )
)


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _chunked(items: list[str], size: int) -> Iterator[tuple[int, list[str]]]:
    for start in range(0, len(items), size):
        yield start // size, items[start : start + size]


class _RateLimiter:
    """Sliding-window limiter: at most ``per_minute`` acquisitions in any 60s window."""

    def __init__(self, per_minute: int) -> None:
        self._per_minute = per_minute
        self._calls: deque[float] = deque()

    def acquire(self) -> None:
        while True:
            now = time.monotonic()
            while self._calls and now - self._calls[0] > 60:
                self._calls.popleft()
            if len(self._calls) < self._per_minute:
                self._calls.append(now)
                return
            time.sleep(60 - (now - self._calls[0]) + 0.05)


def _call_with_retry(limiter: _RateLimiter, fn: Callable[[], T]) -> T:
    """The SDK transport already retries 429/5xx a few times; this layer survives longer outages."""
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        limiter.acquire()
        try:
            return fn()
        except FATAL:
            raise
        except RateLimitError as err:
            wait = min(RETRY_MAX_SECONDS, err.retry_after or RETRY_BASE_SECONDS * 2 ** (attempt - 1))
            _log(f"  rate limited, retrying in {wait:.0f}s ({attempt}/{RETRY_ATTEMPTS})")
            time.sleep(wait)
        except DiscolikeError as err:
            if attempt == RETRY_ATTEMPTS:
                raise
            _log(f"  {type(err).__name__}: {err} - retry {attempt}/{RETRY_ATTEMPTS}")
            time.sleep(RETRY_BASE_SECONDS * attempt)
    raise RuntimeError("unreachable: retries exhausted without raising")


def _drop_managed(kwargs: dict[str, Any], managed: tuple[str, ...]) -> dict[str, Any]:
    for key in managed:
        if key in kwargs:
            _log(f"note: {key} is managed by bulk, ignoring the supplied value")
            kwargs.pop(key)
    return kwargs


def _client(ctx: typer.Context) -> Discolike:
    from discolike_cli.main import get_client

    return get_client(ctx).with_options(timeout=CLIENT_TIMEOUT_SECONDS)


# --------------------------------------------------------------------------- companies


@app.command("companies")
@handle_errors
def companies_command(
    ctx: typer.Context,
    icp_prompt: str | None = typer.Option(None, help="Natural-language ideal customer profile description."),
    domain: list[str] | None = typer.Option(None, help="Seed domain for lookalike matching (repeatable)."),
    phrase_match: list[str] | None = typer.Option(None, help="Phrase the company website must contain (repeatable)."),
    negate_phrase_match: list[str] | None = typer.Option(None, help="Negate the --phrase-match filter (repeatable)."),
    category: list[str] | None = typer.Option(None, help="Industry category filter (repeatable)."),
    country: list[str] | None = typer.Option(None, help="ISO country code filter (repeatable)."),
    state: list[str] | None = typer.Option(None, help="State or region filter (repeatable)."),
    employee_range: str | None = typer.Option(None, help="Employee count range filter."),
    revenue_range: str | None = typer.Option(None, help="Revenue range filter."),
    variance: str | None = typer.Option(
        None, help="Result diversity: LOW, MID_LOW, MEDIUM, MID_HIGH, HIGH, UNRESTRICTED."
    ),
    exclusion_query_id: list[str] | None = typer.Option(None, help=EXCLUSION_QUERY_ID_HELP),
    param: list[str] | None = typer.Option(None, "--param", help=PARAM_HELP),
    params_file: pathlib.Path | None = typer.Option(None, help=PARAMS_FILE_HELP),
    max_companies: int = typer.Option(MAX_RECORDS, help="Stop once this many companies are in --out."),
    page_size: int = typer.Option(MAX_RECORDS, min=MIN_RECORDS, max=MAX_RECORDS, help="Companies per discover call."),
    run_name: str = typer.Option("bulk", help="Prefix for the exclusion lists created per page (<run-name>-round-N)."),
    out: pathlib.Path = typer.Option(
        pathlib.Path("companies.csv"), help="CSV to append each page to; resumes if present."
    ),
    overwrite: bool = typer.Option(False, "--overwrite", help=OVERWRITE_HELP),
    rate_limit: int = typer.Option(DEFAULT_RATE_LIMIT_PER_MINUTE, help=RATE_LIMIT_HELP),
) -> None:
    """Walk the company index past 10,000 results, one exclusion list per page, appending to a CSV."""
    base = _drop_managed(
        _merge_params(
            param,
            params_file,
            icp_prompt=icp_prompt,
            domain=domain,
            phrase_match=phrase_match,
            negate_phrase_match=negate_phrase_match,
            category=category,
            country=country,
            state=state,
            employee_range=employee_range,
            revenue_range=revenue_range,
            variance=variance,
        ),
        COMPANIES_MANAGED,
    )
    build_request(DiscoverParams, {**base, "max_records": page_size})  # fail on a typo before any billable call
    if not any(base.get(key) for key in ("icp_prompt", "icp_text", "domain")):
        _log("warning: no icp_prompt / icp_text / seed --domain set - results are filter-only, unranked")

    seen: list[str] = []
    if out.exists() and not overwrite:
        seen = read_domains_file(out)
        _log(f"resuming: {len(seen):,} companies already in {out}")
    seen_set = set(seen)

    client = _client(ctx)
    limiter = _RateLimiter(rate_limit)
    exclusion_ids: list[str] = list(exclusion_query_id or [])
    inline_excludes: list[str] = []

    def arm_exclusion(domains: list[str], label: str) -> None:
        if len(domains) < MIN_EXCLUSION_LIST:
            inline_excludes.extend(domains)
            return
        request = CreateExclusionListRequest(query_name=label, domains=domains)
        result = _call_with_retry(limiter, functools.partial(client.queries.create_exclusion_list, request))
        exclusion_ids.append(str(result.query_id))

    if seen and not exclusion_ids:
        for index, batch in _chunked(seen, MAX_RECORDS):
            arm_exclusion(batch, f"{run_name}-resume-{index}")
        _log(
            f"re-armed {len(exclusion_ids)} exclusion list(s) from the existing file "
            "(pass the original --exclusion-query-id values to reuse them instead)"
        )

    added = 0
    rounds = 0
    with out.open("a" if seen else "w", newline="") as handle:
        writer = csv.writer(handle)
        if not seen:
            writer.writerow(COMPANY_COLUMNS)
        while len(seen) < max_companies:
            rounds += 1
            want = min(page_size, max_companies - len(seen))
            request = build_request(
                DiscoverParams,
                {
                    **base,
                    "exclusion_query_id": exclusion_ids or None,
                    "exclude_domain": inline_excludes or None,
                    "max_records": max(MIN_RECORDS, want),
                },
            )
            companies = _call_with_retry(limiter, functools.partial(client.discover, request))
            fresh = [c for c in companies if c.domain and c.domain not in seen_set][: max_companies - len(seen)]
            for company in fresh:
                assert company.domain is not None
                seen.append(company.domain)
                seen_set.add(company.domain)
                writer.writerow(
                    [
                        company.domain,
                        company.name,
                        company.address.country if company.address else None,
                        company.employees,
                        company.similarity,
                    ]
                )
            handle.flush()
            added += len(fresh)
            _log(f"round {rounds}: +{len(fresh):,} net-new ({len(seen):,} total)")
            if not fresh:
                _log("no net-new companies left for this ICP - stopping")
                break
            if len(companies) < want:
                _log("search returned less than requested - full set reached")
                break
            if len(seen) >= EXCLUSION_CAPACITY:
                _log(f"warning: {len(seen):,} companies is at the exclusion capacity; slice the ICP into separate runs")
            arm_exclusion([c.domain for c in fresh if c.domain], f"{run_name}-round-{rounds}")

    emit(
        {
            "companies": len(seen),
            "new": added,
            "rounds": rounds,
            "exclusion_query_ids": exclusion_ids,
            "out": str(out),
        }
    )


# --------------------------------------------------------------------------- contacts / estimate


def _contact_filters(
    param: list[str] | None,
    params_file: pathlib.Path | None,
    *,
    icp_prompt: str | None,
    summary: str | None,
    negate_summary: str | None,
    seniority: list[str] | None,
    negate_seniority: list[str] | None,
    department: list[str] | None,
    negate_department: list[str] | None,
    title: list[str] | None,
    negate_title: list[str] | None,
    person_country: list[str] | None,
    person_state: list[str] | None,
    has_email: bool,
    exclusion_query_id: list[str] | None,
) -> dict[str, Any]:
    return _drop_managed(
        _merge_params(
            param,
            params_file,
            icp_prompt=icp_prompt,
            summary=summary,
            negate_summary=negate_summary,
            seniority=seniority,
            negate_seniority=negate_seniority,
            department=department,
            negate_department=negate_department,
            title=title,
            negate_title=negate_title,
            person_country=person_country,
            person_state=person_state,
            has_email=has_email,
            exclusion_query_id=exclusion_query_id,
        ),
        CONTACTS_MANAGED,
    )


def _flatten(company: dict[str, Any], contact: dict[str, Any]) -> dict[str, Any]:
    phones = contact.get("phone") or []
    first_phone = phones[0] if phones else None
    linkedin = next((url for url in (contact.get("social_urls") or []) if "linkedin.com" in url), None)
    name = contact.get("name") or ""
    first, _, last = name.partition(" ")
    return {
        "persona_id": contact.get("persona_id"),
        "first_name": contact.get("first_name") or first,
        "last_name": contact.get("last_name") or last,
        "name": name,
        "title": contact.get("title"),
        "seniority": contact.get("seniority"),
        "department": contact.get("department"),
        "email": contact.get("email"),
        "email_validated": contact.get("email_validated"),
        "phone": first_phone.get("phone") if isinstance(first_phone, dict) else first_phone,
        "linkedin": linkedin,
        "connections": contact.get("connections"),
        "domain": company.get("domain"),
        "company_name": company.get("name") or contact.get("company_name"),
        "country": contact.get("country"),
        "state": contact.get("state"),
        "industry": ";".join(contact.get("industry") or []),
        "employees": contact.get("employees") or company.get("employees"),
        "revenue_range": contact.get("revenue_range") or company.get("revenue_range"),
        "jobstart_date": contact.get("jobstart_date"),
    }


def _persona_ids_in(path: pathlib.Path) -> set[str]:
    """Rows already in the CSV, so a rerun after a lost checkpoint never writes a persona twice."""
    if not path.exists():
        return set()
    with path.open(newline="") as handle:
        return {row["persona_id"] for row in csv.DictReader(handle) if row.get("persona_id")}


ICP_PROMPT_HELP = "Natural-language ICP prompt used to derive contact filters."
SUMMARY_HELP = "Filter by profile summary text (semantic search); ranks who comes back per company."
NEGATE_SUMMARY_HELP = "Exclude contacts matching this summary description."
HAS_EMAIL_HELP = "Only contacts with an email address (on by default)."


@app.command("estimate")
@handle_errors
def estimate_command(
    ctx: typer.Context,
    domains_file: pathlib.Path = typer.Option(..., "--domains-file", help=DOMAINS_FILE_HELP),
    per_company: int = typer.Option(10, min=1, max=MAX_PER_COMPANY, help=PER_COMPANY_HELP),
    icp_prompt: str | None = typer.Option(None, help=ICP_PROMPT_HELP),
    summary: str | None = typer.Option(None, help=SUMMARY_HELP),
    negate_summary: str | None = typer.Option(None, help=NEGATE_SUMMARY_HELP),
    seniority: list[str] | None = typer.Option(None, help="Filter by seniority level (repeatable)."),
    negate_seniority: list[str] | None = typer.Option(None, help="Exclude seniority levels (repeatable)."),
    department: list[str] | None = typer.Option(None, help="Filter by department (repeatable)."),
    negate_department: list[str] | None = typer.Option(None, help="Exclude departments (repeatable)."),
    title: list[str] | None = typer.Option(None, help="Filter by job title (repeatable)."),
    negate_title: list[str] | None = typer.Option(None, help="Exclude job titles (repeatable)."),
    person_country: list[str] | None = typer.Option(None, help="Filter by contact country (repeatable)."),
    person_state: list[str] | None = typer.Option(None, help="Filter by contact state/region (repeatable)."),
    has_email: bool = typer.Option(True, "--has-email/--no-has-email", help=HAS_EMAIL_HELP),
    exclusion_query_id: list[str] | None = typer.Option(None, help=EXCLUSION_QUERY_ID_HELP),
    param: list[str] | None = typer.Option(None, "--param", help=PARAM_HELP),
    params_file: pathlib.Path | None = typer.Option(None, help=PARAMS_FILE_HELP),
    rate_limit: int = typer.Option(COUNT_RATE_LIMIT_PER_MINUTE, help="Calls per minute on the free /contacts/count."),
) -> None:
    """Size a contact pull for free: matching contacts across the domain list, and the cap at --per-company."""
    domains = read_domains_file(domains_file)
    base = _contact_filters(
        param,
        params_file,
        icp_prompt=icp_prompt,
        summary=summary,
        negate_summary=negate_summary,
        seniority=seniority,
        negate_seniority=negate_seniority,
        department=department,
        negate_department=negate_department,
        title=title,
        negate_title=negate_title,
        person_country=person_country,
        person_state=person_state,
        has_email=has_email,
        exclusion_query_id=exclusion_query_id,
    )
    build_request(ContactsCountParams, {**base, "domain": domains[:1]})

    client = _client(ctx)
    limiter = _RateLimiter(rate_limit)
    total = 0
    for index, batch in _chunked(domains, COUNT_SLICE):
        request = build_request(ContactsCountParams, {**base, "domain": batch})
        count = _call_with_retry(limiter, functools.partial(client.contacts.count, request))
        total += count.count or 0
        _log(f"  probed {min((index + 1) * COUNT_SLICE, len(domains)):,}/{len(domains):,} companies")
    capped = min(total, len(domains) * per_company)
    _log(f"{len(domains):,} companies | {total:,} matching contacts | ~{capped:,} at {per_company}/company")
    emit(
        {"companies": len(domains), "contacts_available": total, "contacts_capped": capped, "per_company": per_company}
    )


@app.command("contacts")
@handle_errors
def contacts_command(
    ctx: typer.Context,
    domains_file: pathlib.Path = typer.Option(..., "--domains-file", help=DOMAINS_FILE_HELP),
    per_company: int = typer.Option(10, min=1, max=MAX_PER_COMPANY, help=PER_COMPANY_HELP),
    icp_prompt: str | None = typer.Option(None, help=ICP_PROMPT_HELP),
    summary: str | None = typer.Option(None, help=SUMMARY_HELP),
    negate_summary: str | None = typer.Option(None, help=NEGATE_SUMMARY_HELP),
    seniority: list[str] | None = typer.Option(None, help="Filter by seniority level (repeatable)."),
    negate_seniority: list[str] | None = typer.Option(None, help="Exclude seniority levels (repeatable)."),
    department: list[str] | None = typer.Option(None, help="Filter by department (repeatable)."),
    negate_department: list[str] | None = typer.Option(None, help="Exclude departments (repeatable)."),
    title: list[str] | None = typer.Option(None, help="Filter by job title (repeatable)."),
    negate_title: list[str] | None = typer.Option(None, help="Exclude job titles (repeatable)."),
    person_country: list[str] | None = typer.Option(None, help="Filter by contact country (repeatable)."),
    person_state: list[str] | None = typer.Option(None, help="Filter by contact state/region (repeatable)."),
    has_email: bool = typer.Option(True, "--has-email/--no-has-email", help=HAS_EMAIL_HELP),
    exclusion_query_id: list[str] | None = typer.Option(None, help=EXCLUSION_QUERY_ID_HELP),
    param: list[str] | None = typer.Option(None, "--param", help=PARAM_HELP),
    params_file: pathlib.Path | None = typer.Option(None, help=PARAMS_FILE_HELP),
    out: pathlib.Path = typer.Option(
        pathlib.Path("contacts.csv"), help="CSV to append to; <out>.checkpoint tracks slices."
    ),
    overwrite: bool = typer.Option(False, "--overwrite", help=OVERWRITE_HELP),
    rate_limit: int = typer.Option(DEFAULT_RATE_LIMIT_PER_MINUTE, help=RATE_LIMIT_HELP),
) -> None:
    """Pull up to --per-company contacts for every domain in the file into one CSV, resumable by slice."""
    domains = read_domains_file(domains_file)
    per_call = max(1, MAX_RECORDS // per_company)
    slices = list(_chunked(domains, per_call))
    base = _contact_filters(
        param,
        params_file,
        icp_prompt=icp_prompt,
        summary=summary,
        negate_summary=negate_summary,
        seniority=seniority,
        negate_seniority=negate_seniority,
        department=department,
        negate_department=negate_department,
        title=title,
        negate_title=negate_title,
        person_country=person_country,
        person_state=person_state,
        has_email=has_email,
        exclusion_query_id=exclusion_query_id,
    )
    build_request(ContactFilters, {**base, "domain": domains[:1], "results_by_company": per_company})

    checkpoint = out.with_suffix(out.suffix + ".checkpoint")
    if overwrite:
        checkpoint.unlink(missing_ok=True)
        out.unlink(missing_ok=True)
    done: set[int] = set()
    if checkpoint.exists():
        done = {int(line) for line in checkpoint.read_text().split() if line.strip()}
        _log(f"resuming: {len(done)}/{len(slices)} slices already pulled")
    todo = [(index, batch) for index, batch in slices if index not in done]
    _log(f"{len(domains):,} companies | {len(slices)} slice(s) of {per_call} | {len(todo)} to run")

    client = _client(ctx)
    limiter = _RateLimiter(rate_limit)
    seen_personas = _persona_ids_in(out)
    written = 0
    with out.open("a", newline="") as handle, checkpoint.open("a") as checkpoint_handle:
        writer = csv.DictWriter(handle, fieldnames=CONTACT_COLUMNS, extrasaction="ignore")
        if handle.tell() == 0:
            writer.writeheader()
        for index, batch in todo:
            request = build_request(
                ContactFilters,
                {
                    **base,
                    "domain": batch,
                    "results_by_company": per_company,
                    "max_records": max(MIN_RECORDS, min(MAX_RECORDS, len(batch) * per_company)),
                },
            )
            payload = _call_with_retry(limiter, functools.partial(client.contacts.discover, request)).to_dict()
            rows = [
                _flatten(company, contact)
                for company in (payload.get("results") or {}).values()
                for contact in (company.get("contacts") or [])
            ]
            fresh = [row for row in rows if str(row["persona_id"]) not in seen_personas]
            seen_personas.update(str(row["persona_id"]) for row in fresh)
            writer.writerows(fresh)
            handle.flush()
            checkpoint_handle.write(f"{index}\n")
            checkpoint_handle.flush()
            written += len(fresh)
            _log(f"  slice {index + 1}/{len(slices)}: {len(fresh):,} contacts ({written:,} this run)")

    emit(
        {
            "companies": len(domains),
            "slices": len(slices),
            "slices_run": len(todo),
            "contacts": written,
            "out": str(out),
            "checkpoint": str(checkpoint),
        }
    )
