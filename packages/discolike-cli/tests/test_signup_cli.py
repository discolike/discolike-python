from __future__ import annotations

import json
from unittest.mock import patch

from typer.testing import CliRunner

from discolike._config import save_signup_email
from discolike.signup import SignupResult
from discolike_cli.main import app

runner = CliRunner()

_RESULT = SignupResult(
    status="created",
    email="jane@acme.com",
    org_domain="acme.com",
    org_status="created",
    next_step="A confirmation email was sent to jane@acme.com.",
)


def test_signup_calls_sdk_without_client() -> None:
    with patch("discolike_cli.signup.signup", autospec=True, return_value=_RESULT) as sdk_signup:
        result = runner.invoke(
            app, ["signup", "--email", "jane@acme.com", "--first-name", "Jane", "--last-name", "Doe"]
        )
    assert result.exit_code == 0, result.output
    sdk_signup.assert_called_once()
    kwargs = sdk_signup.call_args.kwargs
    assert kwargs["email"] == "jane@acme.com"
    assert kwargs["agent"].startswith("discolike-cli/")
    assert json.loads(result.stdout)["next_step"] == _RESULT.next_step


def test_signup_honours_base_url_option() -> None:
    with patch("discolike_cli.signup.signup", autospec=True, return_value=_RESULT) as sdk_signup:
        result = runner.invoke(
            app,
            [
                "--base-url",
                "https://api.dev.test/v1",
                "signup",
                "--email",
                "j@acme.com",
                "--first-name",
                "J",
                "--last-name",
                "D",
            ],
        )
    assert result.exit_code == 0, result.output
    assert sdk_signup.call_args.kwargs["base_url"] == "https://api.dev.test/v1"


def test_signup_does_not_require_credentials(monkeypatch) -> None:
    monkeypatch.delenv("DISCOLIKE_API_KEY", raising=False)
    with patch("discolike_cli.signup.signup", autospec=True, return_value=_RESULT):
        result = runner.invoke(app, ["signup", "--email", "j@acme.com", "--first-name", "J", "--last-name", "D"])
    assert result.exit_code == 0, result.output


def test_signup_different_email_non_tty_exits_without_calling_sdk() -> None:
    save_signup_email("jane@acme.com")
    with patch("discolike_cli.signup.signup", autospec=True, return_value=_RESULT) as sdk_signup:
        result = runner.invoke(
            app, ["signup", "--email", "other@acme.com", "--first-name", "Other", "--last-name", "Person"]
        )
    assert result.exit_code == 1
    sdk_signup.assert_not_called()
    assert "re-run with --yes" in result.output


def test_signup_different_email_with_yes_allows_new_email() -> None:
    save_signup_email("jane@acme.com")
    other_result = SignupResult(**{**_RESULT.to_dict(), "email": "other@acme.com"})
    with patch("discolike_cli.signup.signup", autospec=True, return_value=other_result) as sdk_signup:
        result = runner.invoke(
            app,
            ["signup", "--email", "other@acme.com", "--first-name", "Other", "--last-name", "Person", "--yes"],
        )
    assert result.exit_code == 0, result.output
    assert sdk_signup.call_args.kwargs["allow_new_email"] is True


def test_signup_different_email_tty_confirm_proceeds(monkeypatch) -> None:
    save_signup_email("jane@acme.com")
    monkeypatch.setattr("discolike_cli.signup._is_interactive", lambda: True)
    other_result = SignupResult(**{**_RESULT.to_dict(), "email": "other@acme.com"})
    with patch("discolike_cli.signup.signup", autospec=True, return_value=other_result) as sdk_signup:
        result = runner.invoke(
            app,
            ["signup", "--email", "other@acme.com", "--first-name", "Other", "--last-name", "Person"],
            input="y\n",
        )
    assert result.exit_code == 0, result.output
    assert sdk_signup.call_args.kwargs["allow_new_email"] is True
