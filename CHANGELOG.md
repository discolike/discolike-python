# Changelog

## Unreleased

- SDK: new `email` resource — `client.email.find_batch` / `find`, with typed `ValidationOutput` / `EnumerationOutput` results and batch/job handles that poll to completion. Verify results carry an optional `reason` (`deliverable`, `catch_all`, `full_inbox`, `greylisted`, `mailbox_disabled`, `no_mailbox`, `no_smtp_connection`, `smtp_error`, `timed_out`), `None` on jobs run by a worker that predates it.
- SDK: `append` and `segment` accept a `query_id` param that resolves saved queries into domains server-side and unions them with any `file`/`domains` given (Starter+). `append.file` and `segment.domains`/`file` are now optional as long as `query_id` is provided. Not yet reflected in `scripts/check_contract.py` since the platform API hasn't deployed this change.
- SDK: `match.company`/`match.bulk` (sync + async) accept an optional `min_match_confidence` param (50-100) to filter out low-confidence matches; omitted by default so the server default governs. Not yet reflected in `scripts/check_contract.py` since the platform API hasn't deployed this change.

## 0.1.1 (2026-07-14)

- SDK + CLI: new `search_providers` and `llm_providers` resources / `search-providers` and `llm-providers` command groups — BYOK provider management (14 routes).
- SDK + CLI: new `jobstart_date` contacts filter on search, count, and discover.
- SDK (breaking): removed deprecated parameter aliases from `discover`/`count` — `nl_match`, `negate_nl_match`, `negate_icp_text`, `exact_match`, `negate_exact_match`, `vendor`, `negate_vendor`, `min_score`, `max_score`, `negate_domain`. Use `icp_text`, `phrase_match`, `tech_stack`, `min_digital_footprint`/`max_digital_footprint`, and `exclude_domain`.
- CLI (breaking): removed `--icp-text` from `discover` and `contacts search`/`count`/`discover` in favor of `--icp-prompt` (`--param icp_text=...` still works; `contacts generate --icp-text` unchanged).
- CLI: `--format json|table` now available on every data-emitting command, including `--wait` job results.
- CLI: negation filters (`--negate-country`, `--negate-seniority`, …) on `discover`, `count`, and the `contacts` commands.
- CLI: help text on every command and option, and a new `--help` banner. 🪩
- SDK: `JobTimeoutError` now says the task is still running server-side and how to resume — DiscoGen tasks may legitimately run for hours (the platform extends the deadline while a task keeps completing items, up to 12h).

## 0.1.0 (2026-07-13)

Initial release, as two packages: `discolike` (SDK) and `discolike-cli` (CLI, depends on `discolike`).

- `discolike`: sync and async SDK (`Discolike`, `AsyncDiscolike`) covering the full public API: discovery, company profiles, contacts, match, append, segment, ICP validation, saved queries, and account. `Job` handles for async endpoints, with `wait()`, `cancel()`, and progress polling.
- `discolike-cli`: the `discolike` command — `auth`, `discover`, `count`, `match`, `company`, `extract`, `contacts`, `discogen`, `append`, `segment`, `validate-icp`, `queries`, and `account`.
- OpenAPI contract drift checker (`scripts/check_contract.py`), run weekly in CI.
