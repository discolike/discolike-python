# Changelog

## 0.1.0 (2026-07-13)

Initial release.

- Sync and async SDK (`Discolike`, `AsyncDiscolike`) covering the full public API: discovery, company profiles, contacts, match, append, segment, ICP validation, saved queries, and account.
- `Job` handles for async endpoints, with `wait()`, `cancel()`, and progress polling.
- `discolike` CLI: `auth`, `discover`, `count`, `match`, `company`, `extract`, `contacts`, `discogen`, `append`, `segment`, `validate-icp`, `queries`, and `account`.
- OpenAPI contract drift checker (`scripts/check_contract.py`), run weekly in CI.
