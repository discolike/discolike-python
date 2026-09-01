from __future__ import annotations

import json
from unittest.mock import patch

from typer.testing import CliRunner

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
