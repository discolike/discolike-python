# discolike-cli

Official CLI for the [DiscoLike API](https://discolike.com) — the `discolike` command from your terminal. Built on the [`discolike`](https://pypi.org/project/discolike/) SDK.

## Installation

```bash
pip install discolike-cli
```

Or run it without installing:

```bash
uvx --from discolike-cli discolike --help
```

Requires Python 3.10+. Installing this package gives you the `discolike` command.

## Authentication

```bash
discolike auth login
```

Opens your browser to log in (add `--no-browser` to print the URL instead, `--port` to pin the loopback port when forwarding over SSH). To use an API key instead, pass `--api-key KEY` or `--method api_key` to be prompted; create a key at [app.discolike.com/account/management/keys](https://app.discolike.com/account/management/keys). You can also set `DISCOLIKE_API_KEY` in the environment instead.

## Quickstart

```bash
discolike discover --icp-prompt "managed IT services for SMBs" --country US --max-records 25
discolike match "Stripe Inc" --city "San Francisco"
discolike match --file companies.csv --name-column company_name --wait
discolike count --phrase-match "book a demo" --country US
discolike company data stripe.com
discolike extract https://stripe.com/enterprise
```

Top-level commands: `discover`, `count`, `match`, `extract`, `validate-icp`, `append`, `segment` — plus `auth`, `bulk`, `company`, `contacts`, `discogen`, `queries`, `account`, `search-providers`, and `llm-providers` command groups.

### Volume pulls

`discolike bulk` walks past the 10,000-per-search ceiling and pulls contacts for a whole domain list into one CSV, with checkpoint and resume:

```bash
discolike bulk companies --params-file form.json --max-companies 50000 --run-name agencies --out companies.csv
discolike bulk estimate  --domains-file companies.csv --per-company 10          # free size check
discolike bulk contacts  --domains-file companies.csv --per-company 10 --summary "growth marketing" --out contacts.csv
```

`companies` saves each page as an exclusion list (`<run-name>-round-N`) and excludes it from the next page; rerunning with the same `--out` resumes from the CSV. `contacts` slices the domain list at `10000 / per-company` domains per call and records finished slices in `<out>.checkpoint`. Both keep one call in flight under `--rate-limit` (default 10/min, the Pro rate on `/discover` and `/contacts`), retry on 429/5xx, and print a JSON summary at the end. Filters come from `--params-file`, `--param` and the common flags; the paging fields are managed for you.

### Conventions

- Results print as JSON to stdout; errors print as JSON (`error`, `message`, `status_code`) to stderr.
- Pass `--format table` for a human-readable table — used automatically when stdout is a TTY.
- Volume inputs come from files: `--domains-file companies.csv` (a `domain` column, or one domain per line) on `queries create-exclusion-list`, `contacts discover|search|count|generate`, `discogen run` and `validate-icp`; `--params-file form.json` (a JSON object of API parameter names, e.g. an app form) on `discover`, `count` and `contacts discover|search|count`; `--exclude-domains-file` on `discover`. Precedence: file < `--param` < flags.
- Async endpoints (`match --file`, `discogen run`, `discogen run-personas`, `segment`, `validate-icp`) take `--wait` to block until the job finishes. Without it, you get a `task_id` back to poll with `discolike discogen status <task_id> --family <family>`. `append` is synchronous — it returns enriched rows directly (or writes CSV bytes to `--output`).

### Exit codes

| Exit code | Meaning |
|---|---|
| 0 | Success |
| 1 | Server error or unexpected failure |
| 2 | Validation error |
| 3 | Authentication or plan-access error |
| 4 | Rate limited |
| 5 | Network error |
| 6 | Not found |

## Links

- **API documentation**: [docs.discolike.com](https://docs.discolike.com)
- **Source**: [github.com/Discolike/discolike-python](https://github.com/Discolike/discolike-python)

## License

[MIT](https://github.com/Discolike/discolike-python/blob/main/LICENSE)
