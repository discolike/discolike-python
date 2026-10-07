# Contributing

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync --all-packages
```

This is a workspace monorepo:

- `packages/discolike` — the SDK
- `packages/discolike-cli` — the CLI
- `packages/discolike-testkit` — shared test fixtures (never published)

## Before opening a PR

```sh
uv run ruff check .
uv run ruff format --check .
uv run ty check packages/discolike/src packages/discolike/tests packages/discolike-cli/src packages/discolike-cli/tests packages/discolike-testkit/src
uv run pytest packages/discolike/tests -q
uv run pytest packages/discolike-cli/tests -q
```

CI runs the same checks across Python 3.11–3.14.

## Branches

Open PRs against `development`. Features land there first and are released to
`main`; releases are published to PyPI automatically when a GitHub release is
created.

CI also validates SDK routes against the live DiscoLike OpenAPI spec
(`scripts/check_contract.py`). PRs from forks are checked against the
production spec.

CI also runs `scripts/gen_requests.py --check` against the dev spec
(`https://api.dev.discolike.com/v1/openapi.json`) — the committed request
models in `discolike.requests` track dev, not prod. The prod spec lags, so
both `check_contract.py` and `gen_requests.py --check` against prod stay red
until the platform deploys; don't regenerate against prod to "fix" it.

## Compatibility

Released SDK versions stay installed long after a new one ships, and they
all talk to the same live API. Keep them working:

- **Response models parse anything a newer server can send.** Models allow
  extra fields (`extra="allow"`). Response enums are open
  (`Literal[...] | str`), never a closed `Literal`. Response fields carry no
  request-side limits (`max_length`, `ge`/`le`). Don't reuse a request model
  as a response field (see `ProspectingRunBrief`). A new response field gets
  a default, so the SDK still parses servers from before it existed.
- **The SDK may be looser than the spec, never stricter.** The contract check
  flags only drift that breaks parsing: the SDK requiring a field the spec
  makes optional, or the spec allowing a type the SDK rejects.
- **Public signatures don't change silently.** Never rename or remove a
  public method, kwarg, exception, or exported name in a patch release. When
  one has to go, keep the old spelling working with a `DeprecationWarning`
  that names the replacement for at least one minor release, and record the
  removal under **Breaking** in `CHANGELOG.md`.
- **New request fields are optional** and omitted from the wire when unset, so
  a newer SDK still works against an API that hasn't deployed them yet.
- **Python support follows upstream EOL.** Drop a version once it reaches
  end of life, as a **Breaking** CHANGELOG line.

## Reporting bugs

Open a GitHub issue with the package name, version, and a minimal
reproduction. For security issues see [SECURITY.md](SECURITY.md).
