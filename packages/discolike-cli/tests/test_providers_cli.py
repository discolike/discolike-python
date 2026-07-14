from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest
from typer.testing import CliRunner

import discolike_cli.main as cli_main
from conftest import make_client
from discolike_cli.main import app

runner = CliRunner()


def _install_build_client(monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response]) -> None:
    monkeypatch.setattr(cli_main, "build_client", lambda **kwargs: make_client(handler))


def test_search_providers_list_hits_collection(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json={"providers": []})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["search-providers", "list"])
    assert result.exit_code == 0, result.output
    assert captured["request"].url.path == "/v1/search-providers"
    assert captured["request"].method == "GET"


def test_search_providers_create_posts_json(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["method"] = request.method
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"integration_id": "sp1", "integration_name": "Tavily"})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(
        app,
        [
            "search-providers",
            "create",
            "--name",
            "Tavily",
            "--provider",
            "tavily",
            "--search-model",
            "tavily/search",
            "--api-key",
            "tvly-key",
        ],
    )
    assert result.exit_code == 0, result.output
    assert captured["path"] == "/v1/search-providers"
    assert captured["method"] == "POST"
    assert captured["body"] == {
        "integration_name": "Tavily",
        "provider": "tavily",
        "search_model": "tavily/search",
        "api_key": "tvly-key",
    }


def test_search_providers_set_default_puts_subroute(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["method"] = request.method
        return httpx.Response(200, json={"message": "ok", "integration_id": "sp2"})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["search-providers", "set-default", "sp2"])
    assert result.exit_code == 0, result.output
    assert captured["path"] == "/v1/search-providers/sp2/default"
    assert captured["method"] == "PUT"


def test_search_providers_delete_emits_deleted(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/search-providers/sp3"
        assert request.method == "DELETE"
        return httpx.Response(200, json={"message": "ok"})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["search-providers", "delete", "sp3"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"deleted": "sp3"}


def test_search_providers_models_hits_models_route(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json={"models": {}})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["search-providers", "models"])
    assert result.exit_code == 0, result.output
    assert captured["request"].url.path == "/v1/search-providers/models"


def test_llm_providers_create_posts_json(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["method"] = request.method
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"message": "created", "integration_id": "llm1"})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(
        app,
        [
            "llm-providers",
            "create",
            "--name",
            "OpenAI",
            "--provider",
            "openai",
            "--api-key",
            "sk-key",
            "--model-name",
            "gpt-4o",
        ],
    )
    assert result.exit_code == 0, result.output
    assert captured["path"] == "/v1/llm-providers/config"
    assert captured["method"] == "POST"
    assert captured["body"] == {
        "integration_name": "OpenAI",
        "provider": "openai",
        "api_key": "sk-key",
        "model_name": "gpt-4o",
    }


def test_llm_providers_update_keeps_null_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["method"] = request.method
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"message": "updated"})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(
        app,
        [
            "llm-providers",
            "update",
            "llm2",
            "--name",
            "Anthropic",
            "--provider",
            "anthropic",
            "--model-name",
            "claude-sonnet-4-5",
        ],
    )
    assert result.exit_code == 0, result.output
    assert captured["path"] == "/v1/llm-providers/config/llm2"
    assert captured["method"] == "PUT"
    assert captured["body"] == {
        "integration_name": "Anthropic",
        "provider": "anthropic",
        "model_name": "claude-sonnet-4-5",
        "api_key": None,
    }


def test_llm_providers_test_connection_posts_body(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"status": "success", "message": "ok"})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(
        app,
        [
            "llm-providers",
            "test-connection",
            "--provider",
            "openai",
            "--api-key",
            "sk-key",
            "--model-name",
            "gpt-4o",
        ],
    )
    assert result.exit_code == 0, result.output
    assert captured["path"] == "/v1/llm-providers/test-connection"
    assert captured["body"] == {
        "integration_name": "cli-test",
        "provider": "openai",
        "api_key": "sk-key",
        "model_name": "gpt-4o",
    }


def test_llm_providers_get_hits_config_item(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json={"integration_id": "llm3", "integration_name": "Anthropic"})

    _install_build_client(monkeypatch, handler)
    result = runner.invoke(app, ["llm-providers", "get", "llm3"])
    assert result.exit_code == 0, result.output
    assert captured["request"].url.path == "/v1/llm-providers/config/llm3"
    assert captured["request"].method == "GET"
