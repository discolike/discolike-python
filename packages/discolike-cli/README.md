# discolike-cli

Official CLI for the [DiscoLike API](https://www.discolike.com) — the `discolike` command from your terminal. Built on the [`discolike`](https://pypi.org/project/discolike/) SDK.

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

Prompts for an API key (or pass `--api-key`) and verifies it against your account. Create a key at [app.discolike.com/account/management/keys](https://app.discolike.com/account/management/keys). You can also set `DISCOLIKE_API_KEY` in the environment instead.

## Quickstart

```bash
discolike discover --icp-text "managed IT services for SMBs" --country US --max-records 25
discolike match "Stripe Inc" --city "San Francisco"
discolike match --file companies.csv --name-column company_name --wait
discolike count --phrase-match "book a demo" --country US
discolike company data stripe.com
discolike extract https://stripe.com/enterprise
```

Top-level commands: `discover`, `count`, `match`, `extract`, `validate-icp`, `append`, `segment` — plus `auth`, `company`, `contacts`, `discogen`, `queries`, and `account` command groups.

### Conventions

- Results print as JSON to stdout; errors print as JSON (`error`, `message`, `status_code`) to stderr.
- Pass `--format table` for a human-readable table — used automatically when stdout is a TTY.
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
