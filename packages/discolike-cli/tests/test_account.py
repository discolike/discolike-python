from __future__ import annotations

import json
from collections.abc import Callable

import httpx
from typer.testing import CliRunner

from discolike_cli.main import app
from discolike_testkit import Handler

runner = CliRunner()


def test_account_usage_hits_usage_endpoint(install_build_client: Callable[[Handler], None]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/usage"
        return httpx.Response(200, json={"requests_mtd": 100, "records_mtd": 500, "spend_mtd": 12.5})

    install_build_client(handler)
    result = runner.invoke(app, ["account", "usage"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"requests_mtd": 100, "records_mtd": 500, "spend_mtd": 12.5}
