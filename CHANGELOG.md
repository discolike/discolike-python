# Changelog

## 0.1.0 (2026-07-13)

Initial release, as two packages: `discolike` (SDK) and `discolike-cli` (CLI, depends on `discolike`).

- `discolike`: sync and async SDK (`Discolike`, `AsyncDiscolike`) covering the full public API: discovery, company profiles, contacts, match, append, segment, ICP validation, saved queries, and account. `Job` handles for async endpoints, with `wait()`, `cancel()`, and progress polling.
- `discolike-cli`: the `discolike` command — `auth`, `discover`, `count`, `match`, `company`, `extract`, `contacts`, `discogen`, `append`, `segment`, `validate-icp`, `queries`, and `account`.
- OpenAPI contract drift checker (`scripts/check_contract.py`), run weekly in CI.
