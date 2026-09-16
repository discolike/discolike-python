from __future__ import annotations

import pytest
from typer.testing import CliRunner

from discolike_cli import _help
from discolike_cli.main import app

runner = CliRunner()


def test_top_level_help_documents_agent_contract() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Output contract" in result.output
    assert "Exit codes" in result.output
    assert "auth_required" in result.output
    assert "DISCOLIKE_API_KEY" in result.output
    # The exit-code table must survive verbatim, one code per line, not reflowed into prose.
    lines = [line.strip() for line in result.output.splitlines()]
    assert any(line.startswith("2  validation_error") for line in lines)
    assert any(line.startswith("6  not_found") for line in lines)


@pytest.mark.parametrize(
    "argv",
    [
        ["discover"],
        ["count"],
        ["match"],
        ["append"],
        ["validate-icp"],
        ["segment"],
        ["extract"],
        ["signup"],
        ["contacts", "search"],
        ["contacts", "generate"],
        ["discogen", "run"],
        ["discogen", "status"],
        ["queries", "create-exclusion-list"],
        ["auth", "login"],
        ["auth", "status"],
        ["account", "usage"],
    ],
)
def test_command_help_documents_output_and_errors(argv: list[str]) -> None:
    result = runner.invoke(app, [*argv, "--help"])
    assert result.exit_code == 0, result.output
    assert "Output (success" in result.output
    assert "Common errors" in result.output
    assert any(line.strip().startswith("Common errors:") for line in result.output.splitlines())


def test_every_command_epilog_is_short() -> None:
    for name, text in _help.COMMAND_EPILOGS.items():
        assert len(text.splitlines()) <= 18, name


def test_version_prints_bare_semver_when_not_a_tty() -> None:
    from importlib.metadata import version

    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == version("discolike-cli")


def test_version_prints_decorated_line_on_a_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    from importlib.metadata import version

    import discolike_cli.main as cli_main

    monkeypatch.setattr(cli_main, "_stdout_is_tty", lambda: True)
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert f"discolike-cli {version('discolike-cli')}" in result.output
