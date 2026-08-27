# discolike

Official Python SDK for the [DiscoLike API](https://discolike.com) — discover lookalike companies, enrich domain lists, match company names to domains, and find contacts, from typed Python.

For the terminal, see [`discolike-cli`](https://pypi.org/project/discolike-cli/) (`pip install discolike-cli` or `uvx --from discolike-cli discolike`).

## Installation

```bash
pip install discolike
```

Requires Python 3.10+.

## Authentication

```bash
export DISCOLIKE_API_KEY="dl_..."
```

Create a key at [app.discolike.com/account/management/keys](https://app.discolike.com/account/management/keys). You can also pass `api_key=...` explicitly to `Discolike()`.

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

`Job.status()` polls without blocking, `Job.cancel()` aborts, and `wait()` raises `JobFailedError` / `JobTimeoutError` on failure.

`JobTimeoutError` is a client-side wait limit only — the task keeps running server-side (large DiscoGen runs can take hours), so call `wait()` again to resume or fetch `status()` later. Cancelled tasks still return results for every item that finished before cancellation. Send one job per list (up to 10,000 domains) rather than splitting into parallel jobs — concurrent DiscoGen jobs share your LLM provider key and slow each other down.

## Links

- **API documentation**: [docs.discolike.com](https://docs.discolike.com)
- **Source**: [github.com/Discolike/discolike-python](https://github.com/Discolike/discolike-python)

## License

[MIT](https://github.com/Discolike/discolike-python/blob/main/LICENSE)
