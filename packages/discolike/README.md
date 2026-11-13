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

### Contacts runs

`client.contacts_run` finds people at companies in four steps: `find_contacts`, `find_missing` (web search at companies with no indexed contact), `review` and `find_emails`. A `step_by_step` run (the default) pauses with `status="waiting"` after each step; `continue_()` starts the next one. `find_emails` bills per result; an optional `email_cap_usd`, given at create or on the continue that enters it, caps that spend, and without one it runs until the account balance runs out.

```python
from discolike.requests import ContactsRunRequest, ContinueRunRequest

run = client.contacts_run.create(
    ContactsRunRequest.model_validate(
        {
            "companies": {"source": "prompt", "icp_text": "Independent dental clinics in Ohio"},
            "people": {"titles": ["Practice Owner", "Office Manager"]},
        }
    )
)
run = client.contacts_run.wait(run.id, follow=True)  # Stops before find_emails: no cap given.
rows = client.contacts_run.rows(run.id)  # Every row, paged for you.
run = client.contacts_run.continue_(run.id, ContinueRunRequest(generation=run.generation, email_cap_usd=20))
```

`companies` takes `{"source": "prompt", "icp_text": ...}` (up to `max_companies`, default 500), `{"source": "domains", "domains": [...]}` or `{"source": "lookalike", "persona_ids": [...]}`. `max_contacts` keeps only the best-fit N contacts across all companies (`per_company` still caps each one), and `auto_stop=False` turns off the relevance cut, keeping every contact up to `per_company`, best fit first; both stay off the wire unless set. `wait(follow=True)` also stops at a failed step, which you continue with `redo=True`. Every continue carries the run's current `generation`; a stale one is a 409 (`ValidationError`), and a run idle for 30 days answers 410. `contacts.search`, `contacts.count` and `contacts.generate` are deprecated in favor of contacts runs; their endpoints sunset on 2026-12-31.

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

## Links

- **API documentation**: [docs.discolike.com](https://docs.discolike.com)
- **Source**: [github.com/Discolike/discolike-python](https://github.com/Discolike/discolike-python)

## License

[MIT](https://github.com/Discolike/discolike-python/blob/main/LICENSE)
