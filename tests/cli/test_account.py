from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest
from typer.testing import CliRunner

import discolike.cli.main as cli_main
from conftest import make_client
from discolike.cli.main import app

runner = CliRunner()


def _install_build_client(monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response]) -> None:
    monkeypatch.setattr(cli_main, "build_client", lambda **kwargs: make_client(handler))


def test_account_usage_hits_usage_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/usage"
        return httpx.Response(200, json={"requests_mtd": 100, "records_mtd": 500, "spend_mtd": 12.5})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["account", "usage"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"requests_mtd": 100, "records_mtd": 500, "spend_mtd": 12.5}
