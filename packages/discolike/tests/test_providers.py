from __future__ import annotations

import json

import httpx2
import pytest

from discolike_testkit import AsyncClientFactory
from discolike_testkit import ClientFactory


def test_search_providers_list_hits_collection(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        return httpx2.Response(200, json={"providers": [{"integration_id": "sp1"}]})

    with make_client(handler) as client:
        result = client.search_providers.list()

    assert seen["path"] == "/v1/search-providers"
    assert seen["method"] == "GET"
    assert result.providers[0].integration_id == "sp1"


def test_search_providers_create_posts_body_and_drops_unset(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json={"integration_id": "sp2", "integration_name": "Tavily"})

    with make_client(handler) as client:
        result = client.search_providers.create(
            integration_name="Tavily",
            provider="tavily",
            search_model="tavily/search",
            api_key="tvly-key",
        )

    assert seen["path"] == "/v1/search-providers"
    assert seen["method"] == "POST"
    assert seen["body"] == {
        "integration_name": "Tavily",
        "provider": "tavily",
        "search_model": "tavily/search",
        "api_key": "tvly-key",
    }
    assert result.integration_id == "sp2"


def test_search_providers_update_puts_path_and_body(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json={"integration_id": "sp3", "integration_name": "Serper"})

    with make_client(handler) as client:
        result = client.search_providers.update(
            integration_id="sp3",
            integration_name="Serper",
            provider="serper",
            search_model="serper/search",
        )

    assert seen["path"] == "/v1/search-providers/sp3"
    assert seen["method"] == "PUT"
    assert seen["body"] == {
        "integration_name": "Serper",
        "provider": "serper",
        "search_model": "serper/search",
    }
    assert result.integration_name == "Serper"


def test_search_providers_delete_returns_none(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        return httpx2.Response(200, json={"message": "Integration deleted successfully"})

    with make_client(handler) as client:
        result = client.search_providers.delete(integration_id="sp4")

    assert seen["path"] == "/v1/search-providers/sp4"
    assert seen["method"] == "DELETE"
    assert result is None


def test_search_providers_set_default_puts_default_subroute(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        return httpx2.Response(200, json={"message": "ok", "integration_id": "sp5"})

    with make_client(handler) as client:
        result = client.search_providers.set_default(integration_id="sp5")

    assert seen["path"] == "/v1/search-providers/sp5/default"
    assert seen["method"] == "PUT"
    assert result.integration_id == "sp5"


def test_search_providers_clear_default_deletes_default_subroute(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        return httpx2.Response(200, json={"message": "Default search provider cleared successfully"})

    with make_client(handler) as client:
        result = client.search_providers.clear_default(integration_id="sp6")

    assert seen["path"] == "/v1/search-providers/sp6/default"
    assert seen["method"] == "DELETE"
    assert result.message == "Default search provider cleared successfully"


def test_search_providers_models_hits_models_route(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        return httpx2.Response(200, json={"models": {"tavily": [{"name": "tavily/search", "cost_per_query": 0.008}]}})

    with make_client(handler) as client:
        result = client.search_providers.models()

    assert seen["path"] == "/v1/search-providers/models"
    assert seen["method"] == "GET"
    assert result.models["tavily"][0].name == "tavily/search"
    assert result.models["tavily"][0].cost_per_query == 0.008


def test_llm_providers_list_hits_config(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        return httpx2.Response(200, json={"providers": [], "mtime": None})

    with make_client(handler) as client:
        result = client.llm_providers.list()

    assert seen["path"] == "/v1/llm-providers/config"
    assert seen["method"] == "GET"
    assert result.providers == []


def test_llm_providers_create_posts_body_and_drops_unset(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json={"message": "created", "integration_id": "llm1"})

    with make_client(handler) as client:
        result = client.llm_providers.create(
            integration_name="OpenAI",
            provider="openai",
            api_key="sk-key",
            model_name="gpt-4o",
        )

    assert seen["path"] == "/v1/llm-providers/config"
    assert seen["method"] == "POST"
    assert seen["body"] == {
        "integration_name": "OpenAI",
        "provider": "openai",
        "api_key": "sk-key",
        "model_name": "gpt-4o",
    }
    assert result.integration_id == "llm1"


def test_llm_providers_get_hits_config_item(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        return httpx2.Response(200, json={"integration_id": "llm2", "integration_name": "Anthropic"})

    with make_client(handler) as client:
        result = client.llm_providers.get(integration_id="llm2")

    assert seen["path"] == "/v1/llm-providers/config/llm2"
    assert seen["method"] == "GET"
    assert result.integration_name == "Anthropic"


def test_llm_providers_update_keeps_null_api_key_in_body(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json={"message": "updated"})

    with make_client(handler) as client:
        result = client.llm_providers.update(
            integration_id="llm3",
            integration_name="Anthropic",
            provider="anthropic",
            model_name="claude-sonnet-4-5",
        )

    assert seen["path"] == "/v1/llm-providers/config/llm3"
    assert seen["method"] == "PUT"
    assert seen["body"] == {
        "integration_name": "Anthropic",
        "provider": "anthropic",
        "model_name": "claude-sonnet-4-5",
        "api_key": None,
    }
    assert result.message == "updated"


def test_llm_providers_update_sends_new_api_key(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json={"message": "updated"})

    with make_client(handler) as client:
        client.llm_providers.update(
            integration_id="llm3",
            integration_name="Anthropic",
            provider="anthropic",
            model_name="claude-sonnet-4-5",
            api_key="sk-new",
        )

    assert seen["body"]["api_key"] == "sk-new"


def test_llm_providers_delete_returns_none(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        return httpx2.Response(200, json={"message": "Integration deleted successfully"})

    with make_client(handler) as client:
        result = client.llm_providers.delete(integration_id="llm4")

    assert seen["path"] == "/v1/llm-providers/config/llm4"
    assert seen["method"] == "DELETE"
    assert result is None


def test_llm_providers_set_default_posts_subroute(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        return httpx2.Response(200, json={"message": "ok", "integration_id": "llm5"})

    with make_client(handler) as client:
        result = client.llm_providers.set_default(integration_id="llm5")

    assert seen["path"] == "/v1/llm-providers/config/llm5/set-default"
    assert seen["method"] == "POST"
    assert result.integration_id == "llm5"


def test_llm_providers_test_connection_posts_body(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json={"status": "success", "message": "Connection to openai successful"})

    with make_client(handler) as client:
        result = client.llm_providers.test_connection(
            integration_name="probe",
            provider="openai",
            api_key="sk-key",
            model_name="gpt-4o",
            base_url="https://proxy.example.com",
        )

    assert seen["path"] == "/v1/llm-providers/test-connection"
    assert seen["method"] == "POST"
    assert seen["body"] == {
        "integration_name": "probe",
        "provider": "openai",
        "api_key": "sk-key",
        "model_name": "gpt-4o",
        "base_url": "https://proxy.example.com",
    }
    assert result.status == "success"


@pytest.mark.asyncio
async def test_search_providers_list_async(make_async_client: AsyncClientFactory) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"providers": []})

    async with make_async_client(handler) as client:
        result = await client.search_providers.list()

    assert result.providers == []


@pytest.mark.asyncio
async def test_search_providers_set_default_async(make_async_client: AsyncClientFactory) -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        return httpx2.Response(200, json={"message": "ok", "integration_id": "sp7"})

    async with make_async_client(handler) as client:
        result = await client.search_providers.set_default(integration_id="sp7")

    assert seen["path"] == "/v1/search-providers/sp7/default"
    assert seen["method"] == "PUT"
    assert result.integration_id == "sp7"


@pytest.mark.asyncio
async def test_llm_providers_create_async(make_async_client: AsyncClientFactory) -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json={"message": "created", "integration_id": "llm6"})

    async with make_async_client(handler) as client:
        result = await client.llm_providers.create(
            integration_name="OpenAI",
            provider="openai",
            api_key="sk-key",
            model_name="gpt-4o",
        )

    assert seen["path"] == "/v1/llm-providers/config"
    assert seen["body"]["provider"] == "openai"
    assert result.integration_id == "llm6"


@pytest.mark.asyncio
async def test_llm_providers_update_async_keeps_null_api_key(make_async_client: AsyncClientFactory) -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json={"message": "updated"})

    async with make_async_client(handler) as client:
        await client.llm_providers.update(
            integration_id="llm7",
            integration_name="Anthropic",
            provider="anthropic",
            model_name="claude-sonnet-4-5",
        )

    assert seen["body"]["api_key"] is None


def test_route_metadata_stamped() -> None:
    from discolike.resources._base import get_discolike_route
    from discolike.resources.providers import LLMProvidersResource
    from discolike.resources.providers import SearchProvidersResource

    assert get_discolike_route(SearchProvidersResource.list) == ("GET", "/search-providers", True, ())
    assert get_discolike_route(SearchProvidersResource.create) == ("POST", "/search-providers", True, ())
    assert get_discolike_route(SearchProvidersResource.update) == (
        "PUT",
        "/search-providers/{integration_id}",
        True,
        (),
    )
    assert get_discolike_route(SearchProvidersResource.delete) == (
        "DELETE",
        "/search-providers/{integration_id}",
        True,
        (),
    )
    assert get_discolike_route(SearchProvidersResource.set_default) == (
        "PUT",
        "/search-providers/{integration_id}/default",
        True,
        (),
    )
    assert get_discolike_route(SearchProvidersResource.clear_default) == (
        "DELETE",
        "/search-providers/{integration_id}/default",
        True,
        (),
    )
    assert get_discolike_route(SearchProvidersResource.models) == ("GET", "/search-providers/models", True, ())
    assert get_discolike_route(LLMProvidersResource.list) == ("GET", "/llm-providers/config", True, ())
    assert get_discolike_route(LLMProvidersResource.create) == ("POST", "/llm-providers/config", True, ())
    assert get_discolike_route(LLMProvidersResource.get) == ("GET", "/llm-providers/config/{integration_id}", True, ())
    assert get_discolike_route(LLMProvidersResource.update) == (
        "PUT",
        "/llm-providers/config/{integration_id}",
        True,
        (),
    )
    assert get_discolike_route(LLMProvidersResource.delete) == (
        "DELETE",
        "/llm-providers/config/{integration_id}",
        True,
        (),
    )
    assert get_discolike_route(LLMProvidersResource.set_default) == (
        "POST",
        "/llm-providers/config/{integration_id}/set-default",
        True,
        (),
    )
    assert get_discolike_route(LLMProvidersResource.test_connection) == (
        "POST",
        "/llm-providers/test-connection",
        True,
        (),
    )
