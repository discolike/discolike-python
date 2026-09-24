"""The console entry point wraps every parser failure in the JSON error envelope."""

from __future__ import annotations

import json
import pathlib

import pytest

from discolike_cli.main import run


def _run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    with pytest.raises(SystemExit) as raised:
        run(argv)
    captured = capsys.readouterr()
    code = raised.value.code
    return (code if isinstance(code, int) else 1), captured.out, captured.err


@pytest.mark.parametrize(
    ("argv", "fragment"),
    [
        (["count", "--nope"], "--nope"),
        (["discover", "--max-records", "abc"], "not a valid integer"),
        (["discogen", "status"], "TASK_ID"),
        (["auth", "login", "--method", "bogus"], "--method"),
    ],
)
def test_parser_errors_use_the_json_envelope(
    argv: list[str], fragment: str, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, err = _run(argv, capsys)
    assert code == 2
    assert out == ""
    payload = json.loads(err)
    assert payload["code"] == "validation_error"
    assert payload["error"] == "ValidationError"
    assert payload["exit_code"] == 2
    assert fragment in payload["message"]


def test_help_still_renders(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, err = _run(["--help"], capsys)
    assert code == 0
    assert "Exit codes" in out
    assert err == ""


def test_subcommand_help_still_renders(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = _run(["count", "--help"], capsys)
    assert code == 0
    assert "Output (success" in out


def test_bare_invocation_prints_help_not_an_envelope(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, err = _run([], capsys)
    assert code in (0, 2)
    assert "Usage" in out + err
    assert not err.startswith("{")


def test_version_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = _run(["--version"], capsys)
    assert code == 0
    assert out.strip()


def test_api_errors_keep_their_exit_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("DISCOLIKE_API_KEY", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))  # empty: no config file, no credential
    code, _, err = _run(["count", "--country", "US"], capsys)
    assert code == 3
    assert json.loads(err)["code"] == "auth_required"


def test_keyboard_interrupt_exits_130(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    import discolike_cli.main as cli_main

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(cli_main, "app", _boom)
    code, _, _ = _run(["count"], capsys)
    assert code == 130
