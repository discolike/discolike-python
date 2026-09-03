# Changelog

## Unreleased

- SDK (behavior change, no code change): company `address.state` now comes back from the API as the subdivision name ("California", "Tokyo") instead of the ISO code ("CA", "13"). `CompanyAddress.state` is still `str | None` and needs no migration, but anything joining or grouping on that value as a code has to resolve it. The contact's own `state` is unchanged and stays a code.
- SDK: state filters accept a code or a name, resolved server-side against the countries you selected. Discover/count still take one `country` value, but that value may be a region alias (`EU`, `APAC`, `DACH`) and the state resolves against every member. Contacts state filters accept multiple countries and drop a value they cannot resolve rather than erroring.
- SDK: `MatchCompanyParams.state` works for any country with subdivisions, not just the US, and takes a code or a name.
- SDK: regenerated request models — the state field descriptions above now ship in `discolike.requests`.

## 0.3.2 (2026-09-02)

- CLI: every SDK request field now has a flag — `discover`/`count` gain `--variance`, `--min-similarity`, `--consensus`, `--inclusion-query-id`, `--language`, `--social`, `--subdomain`, `--start-date`, `--redirect`, `--exclude-leadgen` and the `--auto-*` toggles; contacts `search`/`count`/`discover` gain the full filter set; `match` gains per-column flags for file mode and `--min-match-confidence`; `append`/`segment` take `--query-id`; `extract` accepts `--domain`. Dict-typed fields stay `--param` only.
- SDK: `CountParams.exclude_leadgen` now defaults to `False`, matching the platform's `/count` default — counts no longer drop suspected lead-gen sites unless you ask for it. Discover is unchanged.

## 0.3.1 (2026-09-02)

- SDK: `discolike.signup()` / `discolike.async_signup()` create a DiscoLike account for a person from their work email and name, with no credential required. Returns `SignupResult` with the `next_step` text to relay.
- CLI: `discolike signup --email --first-name --last-name` does the same from the terminal, without `discolike auth login`. The CLI remembers the last email signed up from this machine and asks before signing up a different one (`--yes` skips the prompt). `discolike auth login` asks first whether you already have an account and offers signup if not.
- SDK: `signup()` / `async_signup()` always post to `base_url` (the DiscoLike API by default); an injected `http_client=` is used as transport only, and its own base URL never redirects the signup request.
- SDK: `AppendParams.dataset` accepts the new `subdomains` dataset — appends the subdomains observed for each domain (up to 300, most popular first).
- SDK: OAuth token requests (PKCE authorization URL, code exchange, refresh) now go through [Authlib](https://authlib.org) 1.8.0's httpx2 client instead of hand-rolled request building; `authlib` is a new dependency. Bearer handling, proactive refresh, the single 401 replay, config persistence, and error types are unchanged. Refreshes use a dedicated token-endpoint client with a 30s timeout rather than the SDK's `http_client`, so proxies or transports configured on `http_client=` no longer apply to the token endpoint.

## 0.3.0 (2026-08-29)

- SDK: OAuth login. `Discolike(auth=...)` / `AsyncDiscolike(auth=...)` accept an `ApiKeyCredential` or `OAuthCredential` (both exported from `discolike`); `api_key=`, `DISCOLIKE_API_KEY`, and the config file keep working unchanged, and `auth=` wins over all of them. OAuth credentials send `Authorization: Bearer`, refresh proactively within 60s of expiry and once more after a 401, and write rotated refresh tokens back to the config file when they were loaded from it (an injected `auth=` is never persisted). A refresh that fails raises `AuthenticationError("OAuth session expired; run `discolike auth login`")`. Config file gains the shape `{"auth_method": "oauth", "oauth": {...}}` next to the existing `api_key` shape.
- SDK: `http_client=` now has its `.auth` set by the SDK (the `X-discolike-key` header moved from a static default header into an `httpx2.Auth`); an `auth` already set on a user-supplied client is replaced.
- CLI: `discolike auth login` now logs in through the browser by default (PKCE authorization-code flow against the platform's OAuth server, loopback redirect on `127.0.0.1`). `--no-browser` prints the URL only, `--port` pins the loopback port for SSH forwarding, and `--method api_key` (or `--api-key KEY`) keeps the API-key flow, including the prompt. Login-flow failures (timeout, denied consent, state mismatch) exit 1 with `{"error": "LoginError", ...}` on stderr.
- CLI: `discolike auth login` remembers the OAuth client it registered (`oauth_client` in the config file) and reuses it on the next login for the same server, so the browser consent screen is only asked once per machine. `auth logout` drops the credential but keeps the registration (a public PKCE client, not a secret), so the next login skips consent too. If PropelAuth no longer recognises the stored client (`invalid_client` / `unauthorized_client`), login registers a fresh one and retries once.
- CLI: `discolike auth status` adds `method` (`api_key` / `oauth`); for OAuth it reports `expires_at` and `expired` instead of a masked key.

- SDK: `JobStatus` gains `estimated_cost` and `cost_metadata` for DiscoGen-family jobs (`discogen`, `validate_icp`, contacts generate). `cost_metadata` has one entry per `provider/model` and a `search_provider` entry with `queries_executed` / `queries_succeeded` / `est_cost_usd` when a BYOS search provider ran. `search_calls` on the model entries counts only the model's built-in search tool and is `0` on every BYOS run; read `search_provider.queries_executed` to confirm web search happened.

### Request models

- SDK (breaking): every request-taking method now takes a single request model instead of keyword arguments, and validates it locally before any HTTP call — a bad enum value, an out-of-range number, or a missing required field raises `pydantic.ValidationError` instead of a server 422. Models live in `discolike.requests` and are generated from the platform OpenAPI spec (`scripts/gen_requests.py`); query-param routes use `<Resource><Method>Params` (`MatchCompanyParams`, `ContactsSearchParams`, `DiscoverParams`, `CountParams`, `AppendParams`, `SegmentParams`, ...) and JSON-body routes use the platform's own names (`FindEmailRequest`, `ContactFilters`, `DiscoGenProcessRequest`, `UpdateQueryRequest`, ...). Path params and file uploads stay keyword arguments next to the model. Unknown fields pass through to the wire, so the SDK never blocks a platform field it does not know about yet.

  ```python
  # before
  client.match.company(name="Acme Inc", city="Austin", min_match_confidence=80)
  client.email.find_batch(contacts=[{"first_name": "Ada", "last_name": "Lovelace", "domain": "acme.com"}])
  client.queries.update(query_id="q3", query_name="New Name")
  client.segment(domains=["acme.com", "beta.com"], max_segments=5)
  client.segment(file="domains.csv", domain_column="domain")

  # after
  from discolike.requests import FindEmailBatchRequest, MatchCompanyParams, SegmentFileParams, SegmentParams, UpdateQueryRequest

  client.match.company(MatchCompanyParams(name="Acme Inc", city="Austin", min_match_confidence=80))
  client.email.find_batch(FindEmailBatchRequest.model_validate({"requests": [{"first_name": "Ada", "last_name": "Lovelace", "domain": "acme.com"}]}))
  client.queries.update(UpdateQueryRequest(query_name="New Name"), query_id="q3")
  client.segment(SegmentParams(domains="acme.com,beta.com", max_segments=5))
  client.segment_file(SegmentFileParams(domain_column="domain"), file="domains.csv")
  ```

- SDK (breaking): `segment` is split into `client.segment(SegmentParams)` (`GET /segment`, `domains` is the comma-separated string the API takes) and `client.segment_file(SegmentFileParams, file=...)` (`POST /segment`). `email.find_batch` drops its `contacts=` alias for the platform's `requests` field. `append` requires `dataset`, matching the platform.
- SDK (breaking): `GET /segment` sends `query_id` as repeated `query_id=` params (the spec declares it an array) instead of the old comma-joined single value.
- SDK: deprecated parameters (`nl_match`, `min_score`, `negate_domain`, `exact_match`, `vendor`, `revenue_range` on contacts, `negate_icp_text`) are not part of the generated models; they still pass through as extra fields if set explicitly.
- SDK: new `DiscolikeRequest` base (`discolike.DiscolikeRequest`) with `to_wire()`, which sends exactly the fields you set — an explicit `None` goes out as `null` (this is how `llm_providers.update` keeps the stored API key), and unset fields are omitted so server defaults keep governing.
- CLI: request models are built from the same options as before, so no flags change. Two behavior changes: `--param KEY=VALUE` with an unknown key is forwarded to the API (previously exit 2), and any option or `--param` value outside the spec (an unknown `--department`, `--max-records` below the floor, `--match loose`) exits 2 with `{"error": "ValidationError", ...}` on stderr before the request is sent. `discolike append` without `--dataset` now fails this same client-side validation (was optional before; `AppendParams` requires it).
- CI: the contract job also runs `scripts/gen_requests.py --check`, so the committed models fail the build when the platform spec moves.

## 0.2.0 (2026-08-21)

- SDK + testkit (breaking): migrated from `httpx` to [`httpx2`](https://github.com/pydantic/httpx2), Pydantic's maintained continuation of httpx, for timely security updates. `httpx` types are part of the public surface (`http_client=`, `with_options(timeout=)`, the testkit `Handler` alias), so callers must swap `import httpx` for `import httpx2` and pass `httpx2.Client` / `httpx2.AsyncClient` / `httpx2.Timeout`. Note httpx2 verifies TLS against the OS trust store via `truststore` instead of bundled `certifi` roots.
- CLI (fix): `auth login` and `auth status` now honor the global `--base-url` and `--api-key`. Every other command routed through `get_client(ctx)`; these two built their own client, so `--base-url` was ignored and `auth status` reported `"valid": true` for a host it never contacted, while `--api-key` was ignored in favour of the environment or config key. `auth status` gains a third `source` value, `option`, for a key passed explicitly on the command line. An ambient `DISCOLIKE_API_KEY` still does not skip the `auth login` prompt — only an explicit flag does.
- SDK: `email.job(job_id)` accepts `kind="find"|"verify"` (default `"find"`), so verify jobs can be rehydrated — previously every rehydrated job decoded as a find job. `wait()` now returns `EnumerationOutput | ValidationOutput` per the handle's kind. Job and batch results also honor a server-reported `kind` field when present, so a handle rehydrated with the wrong kind still parses each result into the right model.
- SDK: `contacts.count` returns a typed `Count` and `contacts.discover` a typed `ContactsDiscoverResponse` (`results` map of domain → `ContactsByCompany`, `total_contacts`, `total_domains`) — both previously returned a bare passthrough model with everything in `.extra`. `ContactsByCompany` now extends `CompanyProfile` (firmographics + nested `contacts`, `email_pattern`, `email_pattern_confidence`, `email_pattern_guess`), mirroring the platform's `DomainContactsEntry`; it was previously defined but never constructed.
- SDK: the client-level `discover`, `count`, `validate_icp`, `append`, and `segment` methods now declare explicit typed signatures mirroring their underlying resource methods (sync + async) instead of untyped `**kwargs` — misspelled keywords are caught statically and editors autocomplete every parameter.
- SDK: new `client.with_options(timeout=...)` (sync + async) — returns a lightweight client view with a per-request timeout override (float or `httpx2.Timeout`), sharing the parent's connection pool. Client-level rate limiting and pagination stay out by design: the transport already retries 429 honoring `Retry-After`, and search/discover paginate via `offset`/`max_records`.
- CLI: new `discolike email` command group wrapping the SDK email resource — `find FIRST LAST DOMAIN [--known-pattern X]`, `find-batch` (CSV file and/or repeatable `--contact "first,last,domain"`, max 500 per batch), `results BATCH_ID [--kind find|verify]`, and `job JOB_ID`, each with `--wait/--no-wait` polling.
- SDK: `email.find` accepts `known_pattern` (sync + async), matching the platform's `POST /email/find` body. Omitted from the request when unset.
- SDK: email routes are no longer `openapi=False` — the platform now exposes `/email/find`, `/email/find/batch`, and the poll routes in its OpenAPI spec, so `check_contract.py` validates them like every other route.
- Examples: new `examples/` folder with runnable end-to-end scripts — `match_crm_contacts.py` (bulk-match a CRM CSV to personas with resumable checkpointing and website+email domain keys), `find_emails_from_csv.py` (batch email finding), `discover_and_enrich.py` (discover + DiscoGen enrichment). Referenced from the README.
- Packaging: both wheels now ship the MIT license text (`dist-info/licenses/LICENSE`) — it was absent from every release so far, since the only `LICENSE` sat at the repo root, outside either package root.
- Packaging: `discolike-cli` ships `py.typed`, so its annotations are visible to type checkers importing `discolike_cli`. Added classifiers: `Python :: 3 :: Only`, `OS Independent`, `Typing :: Typed`, plus `Libraries :: Python Modules` (SDK) and `Environment :: Console` / `Topic :: Utilities` (CLI). Added `Changelog` and `Issues` project URLs.
- CI: tests also run on Python 3.15 prereleases in a non-blocking job. 3.15 stays out of the supported matrix and classifiers until 3.15.0 final.
- SDK + CLI: new `queries.save_results` (sync + async) and `discolike queries save-results` — save result rows (JSON or CSV file in the CLI) as a reusable saved query, the REST twin of the `save-mcp-query` MCP tool. The CLI validates `--action` against the allowed set.
- SDK + CLI (breaking): removed `companies.metrics` / `companies.history` and the `company metrics` / `company history` commands. The underlying `/metrics` and `/history` API endpoints are deprecated, with removal scheduled for 2026-10-01.
- SDK (breaking): `companies.redirects`, `companies.vendors`, `companies.subsidiaries`, and `companies.public_links` now return a `list` of typed rows (`Redirect`, `Vendor`, `Subsidiary`, `PublicLink`). These endpoints return a JSON array; the SDK was validating that array into a single model and raised `ValidationError` on every live call.
- SDK: `discover` rows, `companies.data`, and match rows now share one typed `CompanyProfile` base mirroring the platform's `CompanyResult` — all 21 firmographic fields (`status`, `address`, `keywords`, `industry_groups`, `business_model`, `revenue_range`, `employees`, `mx_provider`, …), with nested `CompanyStatus` / `CompanyAddress`. `discovery.Company` previously declared 5 of them and `BizData` none.
- SDK: `scripts/check_contract.py` now also diffs mirrored response models against the spec's component schemas in both directions — an SDK field the spec lacks, or a platform field the SDK never declared, both fail the contract run (weekly in CI, and on every PR).
- SDK: response models that were empty passthroughs are now typed — `ExtractResult` (`text`, `language`), `Score` (with nested `ScoreParameters`), `Growth`, `MatchResponse` (`query`, `matches`), `SavedQueries` (`results`, `count`), `SearchProviderList` / `LLMProviderList` (`providers`), `SearchModels` / `DiscogenModels` (`models`). `extra="allow"` still carries anything the API adds.
- SDK: `/extract` no longer returns a `links` map — `companies.extract` results carry `text` and `language` only. Code reading `result.links` breaks against the new API. Not yet reflected in `scripts/check_contract.py` since the platform API hasn't deployed this change.
- SDK: new `email` resource — `client.email.find_batch` / `find`, with typed `ValidationOutput` / `EnumerationOutput` results and batch/job handles that poll to completion. Verify batches are created by the DiscoLike app, not the SDK, and re-attached with `client.email.batch(batch_id, kind="verify")`; their results carry an optional `reason` (`deliverable`, `catch_all`, `full_inbox`, `greylisted`, `mailbox_disabled`, `no_mailbox`, `no_smtp_connection`, `smtp_error`, `timed_out`), `None` on jobs run by a worker that predates it.
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
