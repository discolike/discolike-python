# discolike

Official Python SDK for the [DiscoLike API](https://discolike.com) — discover lookalike companies, enrich domain lists, match company names to domains, and find contacts, from typed Python.

For the terminal, see [`discolike-cli`](https://pypi.org/project/discolike-cli/) (`pip install discolike-cli` or `uvx --from discolike-cli discolike`).

## Installation

```bash
pip install discolike
```

Requires Python 3.11+.

## Authentication

```bash
export DISCOLIKE_API_KEY="dl_..."
```

Create a key at [app.discolike.com/account/management/keys](https://app.discolike.com/account/management/keys). You can also pass `api_key=...` explicitly to `Discolike()`, or run `discolike auth login` from the CLI to log in through the browser — the SDK then picks up the saved OAuth session and refreshes it automatically.

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

## Managed prospecting

`client.prospecting.start(ProspectingBrief(...), idempotency_key="...")` drafts a plan. Call `wait(run_id)`, review its `plan` and `messages`, then approve the returned `plan_version` with `approve(run_id, ProspectingApproveRequest(plan_version=...))`.

`wait()` returns on `proposed`, `needs_input`, `completed`, `failed`, or `cancelled`; timeout stops local polling only. Use `message(run_id, ProspectingMessageRequest(text="..."), idempotency_key="...")` to steer or answer a question, and `get(run_id, ProspectingGetParams(events_after=..., messages_after=...))` for new events and replies. `list(ProspectingListParams(limit=20))` lists recent organization runs, up to 50. `rename(run_id, ProspectingRunUpdate(title="..."))` retitles a run in any status and returns its `list()` summary (titles are 1-80 characters after trimming; result lists it already saved keep their names). `rename(run_id, ProspectingRunUpdate(checkpoints="auto"))` switches a run between Manual (`"ask"`) and Auto (`"auto"`) mid-run; switching to Auto while it waits on a checkpoint answers it with continue. `cancel(run_id)` stops a run and returns it; `delete(run_id)` cancels an active run, then removes it so `list()` omits it and `get()` raises `NotFoundError` (charges already incurred stay). The async client has the same methods with `await`. Import these request models from `discolike.requests`.

`update_plan(run_id, ProspectingPlanSettings(plan_version=..., ...))` changes a proposed plan's `contact_integration_id`, `validation_integration_id`, `search_provider_id` (`"none"` skips web research) and `max_spend_usd` (a USD spending limit on records and per-request fees at the plan's rates; `0` removes it) using option ids from the plan message's `contact_engine`, `company_check_engine` and `search_provider`, then returns the run with a re-estimated plan at a new `plan_version` to approve. It also takes `max_provider_spend_usd` (USD on your own AI and search provider keys; `0` removes it), `target_companies`, `contacts_per_company`, `deliverable` (`"leads"` or `"accounts"`, the checked companies only) and `goal` (`"leads"`, or `"companies"` to work only `target_companies` matching companies); `deliverable` and `goal` are optional on `ProspectingBrief` too. The latest plan message is rewritten in place under the same `seq`, so read it from the returned run's `messages`. An unknown option id is a 422; a run not awaiting approval, a stale `plan_version` or a run that cannot switch to `"accounts"` is a 409. `stop_reason` also reports `candidate_limit`, `credit_limit`, `provider_limit` (AI provider spending limit reached) and `companies_worked` (a `goal="companies"` run finished its companies); `candidates_exhausted` means only that the search ran dry. Runs report `provider_cost_usd` and `pipeline_phase` (`"companies"`, `"people"` or `None`).

Checkpoints: `ProspectingBrief(checkpoints=...)` picks how a run handles its decision points. `"auto"`, the API default, never pauses. A run of 500+ target companies from a brief (not a domain list) checks its first companies before looking up contacts; under 80% fit, auto sharpens the criteria once and continues the run with a notice. Only if the re-pilot fit is still under 20% does it stop with `stop_reason="pilot_failed"` and `pilot_sample` holding the checked companies (`domain`, `name`, `company_fit`, `reason`); start a new run with a sharper brief in that case. If sharpening itself fails, the run continues on the original criteria. A search drifting off target is dropped, a run short of candidates finishes as `candidates_exhausted`, and a met target finishes the run. `"ask"` pauses with `status="needs_input"` and a `stop_reason` in `CHECKPOINT_STOP_REASONS` (`pilot`, `tail_quality`, `short`, `target_reached`, `top_up`, `contacts_review`). `contacts_review` pauses a wave run in both modes after it has checked a wave of companies and found and qualified their contacts, before any email lookup; the question gives the wave's counts and the email estimate, and its replies are "Find emails", "Find more companies first" (absent when no wave has room) and "Finish" (keeps the companies and contacts, no emails). "Find emails" is consent to spend on lookups, so it counts only when sent with `question_seq` set to the review question's `seq`; without it the run asks again. Switching to auto leaves it open, and MCP runs answer Find emails themselves. `top_up` asks before another round of companies when the ones checked yield too few contacts; auto runs that round with a notice unless it would pass a spending limit, and then pauses too. Its replies map to `continue`, `raise` (raise the limit), `shrink` (a smaller round) and `finish`. The latest `kind="question"` message carries `data.suggested_replies` and, at a pilot, `data.sample`; answer with `message()` using a suggested reply's exact text (or free-text steering), then `wait()` again. Pass `question_seq=` (the question message's `seq`) on `ProspectingMessageRequest` with a suggested reply so it answers that question only; if a newer question was posted since, it answers none and the agent says the question changed. Choosing to finish at a checkpoint ends the run with `stop_reason="user_finished"`. `ProspectingApproveRequest(checkpoints=...)` overrides the brief's mode at approval; `None` keeps it. `checkpoints` on the brief is not in the published OpenAPI schema; the SDK sends it anyway.

Omit target counts to infer them from the brief; explicit values override the text. Work caps default to automatic (`0`). Partial results and `saved_query_id` remain available after stopping. Large results are split into several saved contact lists rather than being cut off; `saved_query_ids` carries every list for the run in order, with `saved_query_id` always the first entry, and the parts are final once the run reaches a terminal status. Each list has one row per fit company with its `ICP Fit`, `Confidence`, `Reasoning`, `Segment` and `Customer segment` columns and its people under `contacts`; a company with no contact found has `contacts: []`, and an `"accounts"` run saves company rows only. Customer integration charges apply; work caps do not cap provider dollar spend, `max_provider_spend_usd` does.

## Links

- **API documentation**: [docs.discolike.com](https://docs.discolike.com)
- **Source**: [github.com/Discolike/discolike-python](https://github.com/Discolike/discolike-python)

## License

[MIT](https://github.com/Discolike/discolike-python/blob/main/LICENSE)
