<p align="center">
  <a href="https://www.discolike.com">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://discolike.com/images/logo.svg">
      <img src="https://discolike.com/images/logo-dark.svg" alt="DiscoLike" width="220">
    </picture>
  </a>
</p>

<p align="center">
  <b>Official Python SDK and CLI for the DiscoLike API</b><br>
  The clean data layer for GTM engineers — from the entire web to your ideal target accounts.
</p>

<p align="center">
  <a href="https://pypi.org/project/discolike/"><img src="https://img.shields.io/pypi/v/discolike?color=3367f1" alt="PyPI"></a>
  <a href="https://pypi.org/project/discolike/"><img src="https://img.shields.io/pypi/pyversions/discolike" alt="Python versions"></a>
  <a href="https://github.com/Discolike/discolike-python/actions/workflows/ci.yml"><img src="https://github.com/Discolike/discolike-python/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="License: MIT"></a>
</p>

<p align="center">
  <a href="https://www.discolike.com">Website</a> ·
  <a href="https://docs.discolike.com">API Docs</a> ·
  <a href="https://app.discolike.com/account/management/keys">Get an API key</a> ·
  <a href="https://calendly.com/discolike/introductory-call">Book a demo</a> ·
  <a href="https://www.discolike.com/blog/">Blog</a>
</p>

---

DiscoLike indexes **70M+ business websites worldwide**, analyzed in **50 languages** — roughly **3x the coverage of LinkedIn-dependent databases**. This repo gives you that index from Python or your terminal, as two packages: discover lookalike companies, size segments, enrich domain lists, match messy company names to domains, and find the right contacts.

> **If you're a coding agent:** the fastest integration is the hosted MCP server — `https://api.discolike.com/v1/mcp` (streamable-http, OAuth; ~36 tools). For scripting and pipelines use `pip install discolike` as a library; for the terminal use `pip install discolike-cli` or `uvx --from discolike-cli discolike`, auth via `DISCOLIKE_API_KEY`. Machine-readable API index: `https://docs.discolike.com/llms.txt`.

<p align="center">
  <a href="https://www.discolike.com">
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

Requires Python 3.10+.

## Authentication

Create an API key at [app.discolike.com/account/management/keys](https://app.discolike.com/account/management/keys), then use any of:

```bash
export DISCOLIKE_API_KEY="dl_..."   # environment variable
discolike auth login                # or store it via the CLI
```

```python
client = Discolike(api_key="dl_...")  # or pass it explicitly
```

## Quickstart

```python
from discolike import Discolike

client = Discolike()

companies = client.discover(
    icp_text="Cybersecurity for SMBs, managed IT services, endpoint protection",
    country=["US"],
    max_records=25,
)
for company in companies:
    print(company.domain, company.name, company.similarity)
```

Run DiscoGen research over a set of domains and wait for the result:

```python
job = client.discogen.process(
    query="Recent funding rounds and headcount growth",
    domains=["stripe.com", "adyen.com"],
    web_search=True,
)
result = job.wait()
print(result.results)
```

Size a segment before pulling it:

```python
total = client.count(phrase_match=["book a demo"], country=["US"])
print(total.count)
```

Pull a full company profile:

```python
profile = client.companies.data(domain="stripe.com")
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

async def main() -> None:
    async with AsyncDiscolike() as client:
        companies = await client.discover(icp_text="B2B SaaS for logistics", max_records=10)
        print([c.domain for c in companies])

asyncio.run(main())
```

## CLI

The same API from your terminal, with `--help` on every command:

```bash
discolike auth login
discolike discover --icp-text "managed IT services for SMBs" --country US --max-records 25
discolike match "Stripe Inc" --city "San Francisco"
discolike match --file companies.csv --name-column company_name --wait
discolike count --phrase-match "book a demo" --country US
discolike company data stripe.com
discolike extract https://stripe.com/enterprise
```

Top-level commands: `discover`, `count`, `match`, `extract`, `validate-icp`, `append`, `segment` — plus `auth`, `company`, `contacts`, `discogen`, `queries`, and `account` command groups.

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

## What's in the box

| Surface | What it does |
|---|---|
| `client.discover()` / `client.count()` | Find lookalike companies by ICP text, phrases, tech stack, geo, and 40+ other filters |
| `client.companies` | Company profiles: firmographics, scores, growth, history, redirects, vendors, subsidiaries |
| `client.contacts` | Search, look up, match, and discover contacts at target companies |
| `client.match` | Match company names (plus phone/city/state) to domains — single or bulk CSV |
| `client.append()` | Enrich a CSV of domains with DiscoLike datasets |
| `client.segment()` | Auto-segment a list of domains |
| `client.validate_icp()` | Validate a domain list against an ICP definition |
| `client.queries` | Saved inclusion/exclusion lists for reusable targeting |
| `client.account` | Usage and quota |

All responses are typed [Pydantic](https://docs.pydantic.dev/) models.

### Long-running jobs

Bulk operations (`match.bulk`, `segment`, `validate_icp`, `contacts.bulk_match`) return a `Job` handle instead of blocking:

```python
job = client.segment(domains=["stripe.com", "adyen.com", "checkout.com"])
result = job.wait()
```

`Job.status()` polls without blocking, `Job.cancel()` aborts, and `wait()` raises `JobFailedError` / `JobTimeoutError` on failure.

### Error handling

All errors inherit from `DiscolikeError`:

```python
from discolike import Discolike, RateLimitError, ValidationError

try:
    companies = Discolike().discover(icp_text="fintech infrastructure")
except RateLimitError as err:
    ...
except ValidationError as err:
    ...
```

`AuthenticationError`, `PlanAccessError`, `NotFoundError`, `ServerError`, and `APIConnectionError` cover the rest. Transient failures are retried automatically (3 attempts by default).

### Configuration

| Option | Default | |
|---|---|---|
| `api_key` | `DISCOLIKE_API_KEY` env var, then CLI config file | |
| `base_url` | `https://api.discolike.com/v1` | |
| `timeout` | `60.0` seconds | |
| `max_retries` | `3` | |
| `http_client` | — | Bring your own `httpx.Client` / `httpx.AsyncClient` |

A provided `http_client` is mutated in place (the auth header is stamped on it, and `base_url` is set if it's unset) — use a client dedicated to DiscoLike, not one shared across other services.

## Development

This is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/) with two members: `packages/discolike` (the SDK) and `packages/discolike-cli` (the CLI).

```bash
uv sync --all-packages
uv run pytest packages/discolike/tests
uv run pytest packages/discolike-cli/tests
uv run ruff check .
```

## Support & contact

- **API documentation**: [docs.discolike.com](https://docs.discolike.com)
- **Book a demo**: [calendly.com/discolike/introductory-call](https://calendly.com/discolike/introductory-call)
- **LinkedIn**: [linkedin.com/company/discolike](https://www.linkedin.com/company/discolike/)
- **Issues with this SDK**: [GitHub issues](https://github.com/Discolike/discolike-python/issues)

## License

[MIT](LICENSE)
