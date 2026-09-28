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

Top-level commands: `discover`, `count`, `match`, `extract`, `validate-icp`, `append`, `segment` — plus `auth`, `bulk`, `company`, `contacts`, `discogen`, `prospecting`, `queries`, `account`, `search-providers`, and `llm-providers` command groups.

### Volume pulls

`discolike bulk` walks past the 10,000-per-search ceiling and pulls contacts for a whole domain list into one CSV, with checkpoint and resume:

```bash
discolike bulk companies --params-file form.json --max-companies 50000 --run-name agencies --out companies.csv
discolike bulk estimate  --domains-file companies.csv --per-company 10          # free size check
discolike bulk contacts  --domains-file companies.csv --per-company 10 --summary "growth marketing" --out contacts.csv
```

`companies` saves each page as an exclusion list (`<run-name>-round-N`) and excludes it from the next page; rerunning with the same `--out` resumes from the CSV. `contacts` slices the domain list at `10000 / per-company` domains per call and records finished slices in `<out>.checkpoint`. Both keep one call in flight under `--rate-limit` (default 10/min, the Pro rate on `/discover` and `/contacts`), retry on 429/5xx, and print a JSON summary at the end. Filters come from `--params-file`, `--param` and the common flags; the paging fields are managed for you.

### Managed prospecting

```bash
discolike prospecting start --brief "Find 100 US logistics companies and 3 operations directors each" --idempotency-key logistics-1
discolike prospecting wait RUN_ID
# Review the proposed plan, then approve the exact version you saw:
discolike prospecting approve RUN_ID --plan-version 1
discolike prospecting list --limit 20
discolike prospecting message RUN_ID --text "Make it 250 companies" --idempotency-key logistics-edit-1
discolike prospecting status RUN_ID --events-after 12 --messages-after 8 --limit 100
discolike prospecting cancel RUN_ID
```

`wait` returns on `proposed`, `needs_input`, `completed`, `failed`, or `cancelled`. A timeout stops polling only. Inspect status and stop reason; completion does not guarantee full coverage. Message replies arrive through `status --messages-after`; follow `next_message_seq` and `reply_pending`.

`start` and `approve` default to pausing at checkpoints, like the web chat: a pilot check on large lists (`pilot`), a search drifting off target (`tail_quality`), candidates running out short of the target (`short`), and the target being met (`target_reached`). Pass `--auto` to never pause; a poor pilot is then sharpened once and the run continues with a notice, stopping with `pilot_failed` only if the re-pilot fit is still under 20%. If sharpening itself fails, the run continues on the original criteria. On a terminal, `wait` shows the question, any sample companies and numbered replies at a checkpoint, sends your pick or your own text, and keeps waiting. Without a terminal, or with `--no-input`, it prints the run on stdout, a `needs_input` envelope (`message`, `stop_reason`, `suggested_replies`, `sample`) on stderr, and exits 7; answer with `prospecting message --text "<reply>"` and run `wait` again.

Omit `--target-companies` and `--contacts-per-company` to infer counts from the brief (fallback 25 and 2). Explicit values override the text. `--max-candidates` and `--max-actions` are automatic when omitted or `0`; their maxima are 100,000 and 10,000. Targets allow up to 10,000 companies, status pages up to 500 rows, and lists up to 50 runs. Work caps do not cap provider charges.

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
| 7 | Needs input: `prospecting wait` reached a checkpoint with no terminal to ask (or `--no-input`) |

## Links

- **API documentation**: [docs.discolike.com](https://docs.discolike.com)
- **Source**: [github.com/Discolike/discolike-python](https://github.com/Discolike/discolike-python)

## License

[MIT](https://github.com/Discolike/discolike-python/blob/main/LICENSE)
