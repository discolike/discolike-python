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

CI runs the same checks across Python 3.10–3.14.

## Branches

Open PRs against `development`. Features land there first and are released to
`main`; releases are published to PyPI automatically when a GitHub release is
created.

CI also validates SDK routes against the live DiscoLike OpenAPI spec
(`scripts/check_contract.py`). PRs from forks are checked against the
production spec.

## Reporting bugs

Open a GitHub issue with the package name, version, and a minimal
reproduction. For security issues see [SECURITY.md](SECURITY.md).
