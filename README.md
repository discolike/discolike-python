<p align="center">
  <a href="https://discolike.com">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://discolike.com/images/logo.svg">
      <img src="https://discolike.com/images/logo-dark.svg" alt="DiscoLike" width="220">
    </picture>
  </a>
</p>

<p align="center">
  <b>Official Python SDK and CLI for the DiscoLike API</b><br>
  The search engine for the business web — find your ideal target accounts from Python or your terminal.
</p>

<p align="center">
  <a href="https://pypi.org/project/discolike/"><img src="https://img.shields.io/pypi/v/discolike?color=3367f1" alt="PyPI"></a>
  <a href="https://pypi.org/project/discolike/"><img src="https://img.shields.io/pypi/pyversions/discolike" alt="Python versions"></a>
  <a href="https://github.com/Discolike/discolike-python/actions/workflows/ci.yml"><img src="https://github.com/Discolike/discolike-python/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="License: MIT"></a>
</p>

<p align="center">
  <a href="https://discolike.com">Website</a> ·
  <a href="https://docs.discolike.com">API Docs</a> ·
  <a href="https://app.discolike.com/account/management/keys">Get an API key</a> ·
  <a href="https://discolike.com/signup">Sign up</a> ·
  <a href="https://calendly.com/discolike/introductory-call">Book a demo</a> ·
  <a href="https://discolike.com/blog/">Blog</a>
</p>

---

DiscoLike indexes **80M+ business websites worldwide**, analyzed in **50 languages** — roughly **3x the coverage of LinkedIn-dependent databases**. This repo gives you that index from Python or your terminal, as two packages: discover lookalike companies, size segments, enrich domain lists, match messy company names to domains, and find the right contacts.

> **If you're a coding agent:** you can go from no account to first call without a human at a browser — `discolike.signup()` (or `discolike signup`) opens an account from an email and name, the owner confirms by email, and `discolike auth login` mints a credential. The fastest integration once authenticated is the hosted MCP server — `https://api.discolike.com/v1/mcp` (streamable-http, OAuth; 48 tools). For scripting and pipelines use `pip install discolike` as a library; for the terminal use `pip install discolike-cli` or `uvx --from discolike-cli discolike`, auth via `DISCOLIKE_API_KEY`. Machine-readable API index: `https://docs.discolike.com/llms.txt`.

<p align="center">
  <a href="https://discolike.com">
    <img src="https://discolike.com/images/og-image-default.png" alt="DiscoLike — from the entire web to your ideal target accounts" width="720">
  </a>
</p>

## Installation

This repo ships two packages: [`discolike`](https://pypi.org/project/discolike/) (the SDK) and [`discolike-cli`](https://pypi.org/project/discolike-cli/) (the `discolike` command, depends on the SDK).

```bash
pip install discolike       # SDK only, for use as a library
pip install discolike-cli   # CLI — installs discolike as a dependency
pip install "discolike[cli]"  # same thing, extras spelling
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add discolike               # as a library
uv tool install discolike-cli  # CLI only
```

Or run the CLI without installing:

```bash
uvx --from discolike-cli discolike --help
```

Requires Python 3.11+.

## Authentication

Three ways in, in the order an agent hits them: open an account, log in, or use an API key.

### Signup — no browser, no credential

```bash
discolike signup --email jane@acme.com --first-name Jane --last-name Doe --agent my-agent
```

```python
from discolike import signup

result = signup(email="jane@acme.com", first_name="Jane", last_name="Doe", agent="my-agent")
print(result.next_step)  # relay this to the account owner
```

`async_signup()` is the async twin. Nothing is returned that authenticates you: the account owner confirms by email and logs in at [app.discolike.com](https://app.discolike.com). `SignupResult` carries `status`, `email`, `org_domain`, `org_status`, and the `next_step` text to relay. Names are validated locally (1-40 characters, at least one letter, no angle brackets or control characters) before the request is sent.

`--agent` / `agent=` records which agent or framework opened the account; it defaults to `discolike-python/<version>`. The email of the last signup from this machine is remembered — signing up a different one needs `--yes` on the CLI or `allow_new_email=True` in the SDK, so a looping agent cannot quietly open accounts in a stream of names.

### Login

```bash
discolike auth login              # browser, PKCE authorization code, loopback redirect
discolike auth login --no-browser # print the URL instead of opening one — headless boxes
discolike auth login --port 8765  # pin the loopback port for SSH forwarding
discolike auth login --method api_key   # paste an API key instead
discolike auth status             # method, expiry, key source
```

`auth login` asks first whether you already have an account, and offers signup if not. The registered OAuth client is remembered per machine, so the consent screen appears once; `auth logout` drops the credential and keeps the registration.

### API key

Create one at [app.discolike.com/account/management/keys](https://app.discolike.com/account/management/keys), then use any of:

```bash
export DISCOLIKE_API_KEY="dl_..."   # environment variable
discolike auth login --api-key dl_...  # or store it via the CLI
```

```python
from discolike import ApiKeyCredential, Discolike

client = Discolike()                      # env var, then CLI config file
client = Discolike(api_key="dl_...")      # explicit key
client = Discolike(auth=ApiKeyCredential(api_key="dl_..."))
client = Discolike(auth=oauth_credential)  # an OAuthCredential — Bearer, refreshed proactively
```

`auth=` wins over `api_key=`, the environment, and the config file. OAuth credentials refresh within 60s of expiry and once more after a 401; a refresh that fails raises `AuthenticationError("OAuth session expired; run `discolike auth login`")`.

## Quickstart

```python
from discolike import Discolike
from discolike.requests import DiscoverParams

client = Discolike()

companies = client.discover(
    DiscoverParams(
        icp_text="Cybersecurity for SMBs, managed IT services, endpoint protection",
        country=["US"],
        max_records=25,
    )
)
for company in companies:
    print(company.domain, company.name, company.similarity)
```

Narrow to a sub-industry within a radius of a point:

```python
from discolike import Discolike
from discolike.requests import DiscoverParams

client = Discolike()

roofers = client.discover(
    DiscoverParams(
        sub_industry=["ROOFING"],
        lat=30.2672,
        lon=-97.7431,
        radius="50mi",
        max_records=25,
    )
)
for company in roofers:
    print(company.domain, company.name, company.sub_industry)
```

A bare `ROOFING` resolves to `CONSTRUCTION/ROOFING` and adds `CONSTRUCTION` to the category filter
server-side; pass the qualified form yourself if you would rather be explicit.

One query can cover several areas at once. `geo` takes `lat,lon` or `lat,lon,radius` and `bbox` takes
`min_lat,min_lon,max_lat,max_lon`; both are lists, and every circle, every box and the `lat`/`lon`
centre are OR'd together, up to 10 shapes:

```python
austin_dallas_and_houston = client.discover(
    DiscoverParams(
        sub_industry=["ROOFING"],
        geo=["30.2672,-97.7431,30mi", "32.7767,-96.797,30mi"],
        bbox=["29.6,-95.7,30.1,-95.0"],
        max_records=25,
    )
)
```

Run DiscoGen research over a set of domains and wait for the result:

```python
from discolike.requests import DiscoGenProcessRequest

job = client.discogen.process(
    DiscoGenProcessRequest(
        query="Recent funding rounds and headcount growth",
        domains=["stripe.com", "adyen.com"],
        web_search=True,
    )
)
result = job.wait()
print(result.results)
```

Size a segment before pulling it:

```python
from discolike.requests import CountParams

total = client.count(CountParams(phrase_match=["book a demo"], country=["US"]))
print(total.count)
```

Pull a full company profile:

```python
from discolike.requests import CompaniesDataParams

profile = client.companies.data(CompaniesDataParams(domain="stripe.com"))
```

The client is a context manager if you want deterministic cleanup:

```python
with Discolike() as client:
    ...
```

### Async

Every resource has an async twin on `AsyncDiscolike`:

```python
import asyncio
from discolike import AsyncDiscolike
from discolike.requests import DiscoverParams

async def main() -> None:
    async with AsyncDiscolike() as client:
        companies = await client.discover(DiscoverParams(icp_text="B2B SaaS for logistics", max_records=10))
        print([c.domain for c in companies])

asyncio.run(main())
```

## Examples

The [`examples/`](examples/) folder has runnable scripts for common workflows — matching a CRM contact export to DiscoLike persona IDs (with checkpointing and resume), bulk-finding work emails from a CSV, and discovering companies by ICP then enriching them with DiscoGen. Each is stdlib-plus-SDK only:

```bash
export DISCOLIKE_API_KEY="dl_..."
python examples/match_crm_contacts.py --help
```

## CLI

The same API from your terminal, with `--help` on every command:

```bash
discolike auth login
discolike discover --icp-prompt "managed IT services for SMBs" --country US --max-records 25
discolike match "Stripe Inc" --city "San Francisco"
discolike match --file companies.csv --name-column company_name --wait
discolike count --phrase-match "book a demo" --country US
discolike company data stripe.com
discolike extract https://stripe.com/enterprise
discolike signup --email you@company.com --first-name You --last-name Person
```

Top-level commands: `discover`, `count`, `match`, `extract`, `validate-icp`, `append`, `segment`, `signup` — plus `auth`, `company`, `contacts`, `discogen`, `queries`, `account`, `search-providers`, and `llm-providers` command groups.

### CLI conventions

- Results print as JSON to stdout; errors print as JSON (`error`, `message`, `status_code`) to stderr.
- Pass `--format table` for a human-readable table — used automatically when stdout is a TTY.
- Async endpoints (`match --file`, `discogen run`, `discogen run-personas`, `segment`, `validate-icp`) take `--wait` to block until the job finishes. Without it, you get a `task_id` back to poll with `discolike discogen status <task_id> --family <family>`. `append` is synchronous — it returns enriched rows directly (or writes CSV bytes to `--output`).

| Exit code | Meaning |
|---|---|
| 0 | Success |
| 1 | Server error or unexpected failure |
| 2 | Validation error |
| 3 | Authentication or plan-access error |
| 4 | Rate limited |
| 5 | Network error |
| 6 | Not found |
| 7 | Needs input: `prospecting wait` reached a checkpoint with no terminal to ask (or `--no-input`) |

## What's in the box

| Surface | What it does |
|---|---|
| `client.discover()` / `client.count()` | Find lookalike companies by ICP text, phrases, tech stack, geo, and 40+ other filters |
| `client.companies` | Company profiles: firmographics, scores, growth, redirects, vendors, subsidiaries |
| `client.contacts` | Search, look up, match, and discover contacts at target companies |
| `client.match` | Match company names (plus phone/city/state) to domains — single or bulk CSV |
| `client.append()` | Enrich a CSV of domains with DiscoLike datasets |
| `client.segment()` / `client.segment_file()` | Auto-segment a list of domains (comma-separated string or CSV upload) |
| `client.validate_icp()` | Validate a domain list against an ICP definition |
| `client.queries` | Saved inclusion/exclusion lists for reusable targeting |
| `client.search_providers` / `client.llm_providers` | Manage BYOK search and LLM provider integrations for DiscoGen |
| `client.account` | Usage and quota |
| `discolike.signup()` / `async_signup()` | Open an account from an email and name, no credential required |
| `discolike.requests` | Request models for every call — generated from the platform OpenAPI spec, validated locally before the request is sent |

All responses are typed [Pydantic](https://docs.pydantic.dev/) models.

### Long-running jobs

Bulk operations (`match.bulk`, `segment`, `validate_icp`, `contacts.bulk_match`) return a `Job` handle instead of blocking:

```python
from discolike.requests import SegmentParams

job = client.segment(SegmentParams(domains="stripe.com,adyen.com,checkout.com"))
result = job.wait()
```

`Job.status()` polls without blocking, `Job.cancel()` aborts, and `wait()` raises `JobFailedError` / `JobTimeoutError` on failure. On DiscoGen-family jobs the returned `JobStatus` also carries `warnings`, `estimated_cost` and `cost_metadata` (per-model usage plus a `search_provider` entry when a BYOS search provider ran; `search_calls` only counts the model's built-in search).

`JobTimeoutError` is a client-side wait limit only — the task keeps running server-side (large DiscoGen runs can take hours), so call `wait()` again to resume or fetch `status()` later. Cancelled tasks still return results for every item that finished before cancellation. Send one job per list (up to 10,000 domains) rather than splitting into parallel jobs — concurrent DiscoGen jobs share your LLM provider key and slow each other down.

### Contact generation without an LLM key

`contacts.generate` runs on your own search provider plus either your own LLM or DiscoLike Groove, DiscoLike's native extractor. Pass `NATIVE_ENGINE` to skip the LLM entirely:

```python
from discolike import NATIVE_ENGINE
from discolike.requests import ContactGenerateRequest

job = client.contacts.generate(
    ContactGenerateRequest(
        icp_text="VPs or Directors of Marketing at B2B SaaS",
        domains=["gusto.com", "rippling.com"],
        integration_id=NATIVE_ENGINE,
    )
)
result = job.wait()
print(result.title_validation)  # "none" on the native engine, "llm" on a BYOK run
```

The native engine returns every person the search surfaces with a title and does not validate titles against `icp_text`, so filter them yourself when that matters. Omit `integration_id` to use your default LLM integration, or native when you have none. A search provider is required either way.

### ICP validation without an LLM key

`validate_icp` runs your ICP text against each domain on your own LLM provider key, or on DiscoLike's own ICP-fit model. Pass `NATIVE_ICP_ENGINE` for the latter — no LLM key, no LLM cost, and no web search on that run:

```python
from discolike import NATIVE_ICP_ENGINE
from discolike.requests import ValidateIcpRequest

job = client.validate_icp(
    ValidateIcpRequest(
        icp_text="Cybersecurity for SMBs in North America, 50-500 employees",
        domains=["gusto.com", "rippling.com"],
        integration_id=NATIVE_ICP_ENGINE,
    )
)
print(job.column_name)  # ["ICP Fit", "ICP Score", "Reasoning"]
result = job.wait()
```

The engine decides the result columns, so read `job.column_name` instead of hardcoding them: an LLM run returns `Fit` / `Confidence` / `Reasoning`, the native model `ICP Fit` / `ICP Score` / `Reasoning (always null)`. `ICP Fit` is `Yes` or `No` at a 0.50 threshold on `ICP Score`, the calibrated probability as a 0.00-1.00 string. The native model returns only that score, so `Reasoning` is always `null` — the column is there to keep the set the same shape as an LLM run, not to carry an explanation. `integration_id="native-icp"` also works on `discogen.process` for a prompt that already carries the validation structure.

Two errors are specific to the native engine: a 400 `ValidationError` when the ICP text does not yield a Mandatory / Reject if / Nice-to-have prompt, and a 503 `ServerError` when no ICP-fit engine is available. Task lifecycle, polling and statuses are the same either way.

### Error handling

All errors inherit from `DiscolikeError`:

```python
from discolike import Discolike, RateLimitError, ValidationError
from discolike.requests import DiscoverParams

try:
    companies = Discolike().discover(DiscoverParams(icp_text="fintech infrastructure"))
except RateLimitError as err:
    ...
except ValidationError as err:
    ...
```

`AuthenticationError`, `PlanAccessError`, `NotFoundError`, `ServerError`, and `APIConnectionError` cover the rest. Transient failures are retried automatically (3 attempts by default).

```python
import pydantic
from discolike.requests import MatchCompanyParams

try:
    params = MatchCompanyParams(name="Acme", min_match_confidence=10)
except pydantic.ValidationError as err:
    ...  # raised locally: min_match_confidence must be 50-100
```

Request models validate before anything is sent, so a bad enum value or out-of-range number never costs a round trip. Unknown fields pass through untouched.

### Configuration

| Option | Default | |
|---|---|---|
| `api_key` | `DISCOLIKE_API_KEY` env var, then CLI config file | |
| `base_url` | `https://api.discolike.com/v1` | |
| `timeout` | `60.0` seconds | |
| `max_retries` | `3` | |
| `http_client` | — | Bring your own `httpx2.Client` / `httpx2.AsyncClient` |

A provided `http_client` is mutated in place (the auth header is stamped on it, and `base_url` is set if it's unset) — use a client dedicated to DiscoLike, not one shared across other services.

## Development

This is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/) with two members: `packages/discolike` (the SDK) and `packages/discolike-cli` (the CLI).

```bash
uv sync --all-packages
uv run pytest packages/discolike/tests
uv run pytest packages/discolike-cli/tests
uv run ruff check .
uv run python scripts/gen_requests.py --spec-url https://api.dev.discolike.com/v1/openapi.json  # regenerate request models
uv run python scripts/gen_requests.py --check                                                    # fail on drift (CI)
```

Committed request models track the dev spec (`--spec-url https://api.dev.discolike.com/v1/openapi.json`); the prod spec lags behind, so `--check` without a `--spec-url` (or against prod) stays red until the platform deploys — don't regenerate against prod to "fix" it.

## Support & contact

- **API documentation**: [docs.discolike.com](https://docs.discolike.com)
- **Sign up**: [discolike.com/signup](https://discolike.com/signup)
- **Book a demo**: [calendly.com/discolike/introductory-call](https://calendly.com/discolike/introductory-call)
- **LinkedIn**: [linkedin.com/company/discolike](https://www.linkedin.com/company/discolike/)
- **Issues with this SDK**: [GitHub issues](https://github.com/Discolike/discolike-python/issues)

## License

[MIT](LICENSE)


### Managed prospecting

REST starts in `drafting`, then waits at `proposed` for approval. Review the plan and approve its exact version before research starts.

```python
from discolike.requests import (
    ProspectingApproveRequest, ProspectingBrief, ProspectingGetParams,
    ProspectingListParams, ProspectingMessageRequest, ProspectingPlanSettings, ProspectingRunUpdate,
)

run = client.prospecting.start(
    ProspectingBrief(brief="Find 100 US logistics companies and 3 operations directors each"),
    idempotency_key="logistics-search-2026-09-26",
)
run = client.prospecting.wait(run.run_id)
print(run.status, run.plan, run.messages)  # Review before approving.
# After reviewing a proposed plan:
# client.prospecting.approve(run.run_id, ProspectingApproveRequest(plan_version=run.plan_version))
# run = client.prospecting.wait(run.run_id)

recent = client.prospecting.list(ProspectingListParams(limit=20))
message = client.prospecting.message(
    run.run_id, ProspectingMessageRequest(text="Make it 250 companies"),
    idempotency_key="logistics-target-edit-1",
)
page = client.prospecting.get(
    run.run_id,
    ProspectingGetParams(offset=0, limit=100, events_after=run.next_event_seq, messages_after=run.next_message_seq),
)
# Pick engines or a credit limit from the plan card's options before approving; approve the returned plan_version.
# run = client.prospecting.update_plan(run.run_id, ProspectingPlanSettings(plan_version=run.plan_version, max_spend_usd=25))
# client.prospecting.rename(run.run_id, ProspectingRunUpdate(title="Logistics ops leaders"))  # Any status.
# client.prospecting.rename(run.run_id, ProspectingRunUpdate(checkpoints="auto"))  # Stop pausing; answers an open checkpoint.
# client.prospecting.cancel(run.run_id)  # Stop the run; it and its results stay readable.
# client.prospecting.delete(run.run_id)  # Cancel if active, then remove it from list() and get().
```

The async client exposes the same methods with `await`. Starts and messages require separate idempotency keys; reuse each key when retrying that operation. Approving an already approved version is safe. A stale plan version is rejected: fetch the current plan and review it again.

`wait()` returns on `proposed`, `needs_input`, `completed`, `failed`, or `cancelled`. Inspect `status`, `stop_reason`, and `error`; completion does not guarantee the target was reached. A local timeout stops polling only. Partial results remain available. Use `get()` with event and message cursors to receive the agent's reply after sending a message; `reply_pending` indicates a pending reply. After a "segment these" request on a finished run it stays true past the acknowledgement until the segments message is posted, which can take more than an hour, and clears on its own after about 90 minutes if grouping stops without an outcome. A `needs_input` question can be answered with `message()`.

Checkpoints: `ProspectingBrief(checkpoints=...)` picks how a run handles its decision points. `"auto"`, the API default, never pauses. A run of 500+ target companies from a brief (not a domain list) checks its first companies before looking up contacts; under 80% fit, auto sharpens the criteria once and checks again, then stops with `stop_reason="pilot_failed"` and `pilot_sample` holding the checked companies (`domain`, `name`, `company_fit`, `reason`); start a new run with a sharper brief. A search drifting off target is dropped, a run whose search runs dry finishes as `candidates_exhausted`, and a met target finishes the run. `"ask"` pauses with `status="needs_input"` and a `stop_reason` in `CHECKPOINT_STOP_REASONS` (`pilot`, `tail_quality`, `short`, `target_reached`, `top_up`, `contacts_review`). `contacts_review` pauses a wave run in both modes after it has checked a wave of companies and found and qualified their contacts, before any email lookup; the question gives the wave's counts and the email estimate, and its replies are "Find emails", "Find more companies first" (absent when no wave has room) and "Finish" (keeps the companies and contacts, no emails). "Find emails" is consent to spend on lookups, so it counts only when sent with `question_seq` set to the review question's `seq`; without it the run asks again. Switching to auto leaves it open, and MCP runs answer Find emails themselves. The latest `kind="question"` message carries `data.suggested_replies` and, at a pilot, `data.sample`; answer with `message()` using a suggested reply's exact text (or free-text steering), then `wait()` again. Pass `question_seq=` (the question message's `seq`) on `ProspectingMessageRequest` with a suggested reply so it answers that question only; if a newer question was posted since, it answers none and the agent says the question changed. Choosing to finish at a checkpoint ends the run with `stop_reason="user_finished"`. `ProspectingApproveRequest(checkpoints=...)` overrides the brief's mode at approval; `None` keeps it. `checkpoints` on the brief is not in the published OpenAPI schema; the SDK sends it anyway.

Top-up rounds: when the companies checked so far yield too few contacts for the target, the run sizes another round of companies. `"ask"` pauses on it with `stop_reason="top_up"`; `"auto"` runs it with a notice unless it would pass the run's DiscoLike credit or AI provider spending limit, in which case it pauses too. The question's suggested replies map to `continue` (run another round), `raise` (raise the limit and run it), `shrink` (run the smaller round the limits leave room for) and `finish`; only the ones that apply are offered.

Intake: a run can pause on a `kind="question"` message whose `data` lists a few option fields (keys `company_activity`, `industry`, `geography`, `company_size`, `persona_roles`, `list_size`). Answer it with `client.prospecting.answer_intake(run.run_id, {"company_activity": IntakeAnswer(values=["sell"]), "geography": IntakeAnswer(other="Ohio")}, idempotency_key=...)`: `values` are the option values you picked and `other` is free text. `IntakeAnswer` comes from `discolike.requests`. Invalid answers return 422; an answer sent after the card was superseded returns 409. Typing free text with `message()` instead still works.

Initial planning extracts company counts and contacts per company from the brief. Omitted settings keep that inference available, falling back to 1,000 companies and 3 contacts per company. Explicit settings, including explicit defaults, override the text. Targets support 1–10,000 companies and 1–10 contacts per company. Candidate and action caps default to automatic (`0`); explicit maxima are 100,000 candidates and 10,000 actions. Result pages support up to 500 rows; recent-run lists support up to 50. Approved runs expose a stable `saved_query_id` for saved results.

Run controls: `update_plan(run_id, ProspectingPlanSettings(plan_version=..., ...))` changes a proposed plan before approval. `contact_integration_id`, `validation_integration_id` and `search_provider_id` take an option id from the plan message's `contact_engine`, `company_check_engine` and `search_provider` (`data.contact_engine.options` and so on); omitted fields keep their choice, `search_provider_id="none"` skips web research, and `max_spend_usd` sets the most the run may spend on DiscoLike records and per-request fees, in USD at your plan's rates (`0` removes the limit; a plan with no per-record price is a 422). `max_provider_spend_usd` caps what the run may spend on your own AI and search provider keys, in USD (`0` removes it); once reached the run starts no new work and batches already running finish, so the total can end slightly above it. `target_companies` and `contacts_per_company` resize the plan, and its open limits are re-derived around them. `deliverable` is `"leads"` (find people at the companies) or `"accounts"` (return the checked companies only); `goal` is `"leads"` (keep adding rounds until the contact target is met) or `"companies"` (take `target_companies` matching companies and work only those). The same `deliverable` and `goal` are optional on `ProspectingBrief` at start, both defaulting to `"leads"` server-side, and the run's `brief` reports them. The plan is re-estimated at a new `plan_version`, and that is the version to approve; the latest plan message is rewritten in place under the same `seq`, so read it from the returned run's `messages` rather than past a `messages_after` cursor. An id outside the plan's options is a 422; a run that is not awaiting approval, a stale `plan_version`, or a run that cannot switch to `"accounts"` is a 409. With no engine chosen, contact research runs on DiscoLike Groove when you have a search provider and finds indexed contacts only when you have none. New `stop_reason` values, all plain strings: `candidate_limit` (the run reached its candidate cap; raise `max_candidates` or ask for fewer companies), `credit_limit` (the run stopped at its spending limit and kept its results), `provider_limit` (the run reached its AI provider spending limit), `companies_worked` (a `goal="companies"` run worked through the companies it was asked to take), and `candidates_exhausted` now means only that the search ran dry. A run reports `provider_cost_usd`, what it has spent so far on your AI and search provider keys as the providers report it (`None` when it recorded none; a custom AI endpoint reports no price), and `pipeline_phase`, `"companies"` while a phased run checks companies and `"people"` while it finds people at them (`None` for runs that interleave both).

Saved results: each saved contact list (`saved_query_ids`) holds one row per fit company, carrying its `ICP Fit`, `Confidence`, `Reasoning`, `Segment` and `Customer segment` columns where known, with the people found there under `contacts`. A fit company with no contact found is still saved, with `contacts: []`, and an `"accounts"` run saves company rows only. An automatic candidate cap may grow once from the run's measured yield; a `max_candidates` you set never does. Interrupted indexed contact searches are rerun rather than skipped.

Existing processing charges and configured BYOK/BYOS integrations apply. Wizard interpretation, segmentation, and prompt preparation use platform credentials. Agent coordination and independent contact qualification use your contact LLM integration; native contacts use your validation LLM integration or organization default, so this workflow requires a customer LLM even with native extraction. Missing keys and provider errors never fall back to platform keys. Limits bound work, not provider dollar spend. Email finder outcomes are exposed; raw email verification is not a public API.
