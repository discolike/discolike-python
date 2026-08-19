from __future__ import annotations

import json

import httpx

from discolike_testkit import AsyncClientFactory
from discolike_testkit import ClientFactory


def test_list_sends_params_and_parses_response(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["params"] = httpx.QueryParams(request.url.query)
        return httpx.Response(200, json={"results": [{"query_id": "q1"}], "count": 1})

    with make_client(handler) as client:
        result = client.queries.list(max_records=10, offset=5, action="discover", tags=["a", "b"])

    assert seen["path"] == "/v1/queries/saved"
    assert seen["params"]["max_records"] == "10"
    assert seen["params"]["offset"] == "5"
    assert seen["params"]["action"] == "discover"
    assert seen["params"].get_list("tags") == ["a", "b"]
    assert result.count == 1
    assert result.results[0].query_id == "q1"


def test_create_exclusion_list_posts_json_body(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"query_id": "q2", "query_name": "My List", "domain_count": 2})

    with make_client(handler) as client:
        result = client.queries.create_exclusion_list(query_name="My List", domains=["a.com", "b.com"])

    assert seen["path"] == "/v1/queries/exclusion-list"
    assert seen["method"] == "POST"
    assert seen["body"] == {"query_name": "My List", "domains": ["a.com", "b.com"]}
    assert result.query_id == "q2"


def test_update_patches_path_and_body(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"query_id": "q3", "query_name": "New Name"})

    with make_client(handler) as client:
        result = client.queries.update(query_id="q3", query_name="New Name")

    assert seen["path"] == "/v1/queries/q3"
    assert seen["method"] == "PATCH"
    assert seen["body"] == {"query_name": "New Name"}
    assert result.query_name == "New Name"


def test_delete_sends_delete_and_returns_none(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        return httpx.Response(200, json={"message": "Query deleted successfully"})

    with make_client(handler) as client:
        result = client.queries.delete(query_id="q4")

    assert seen["path"] == "/v1/queries/q4"
    assert seen["method"] == "DELETE"
    assert result is None


async def test_list_async(make_async_client: AsyncClientFactory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": [], "count": 0})

    async with make_async_client(handler) as client:
        result = await client.queries.list()

    assert result.count == 0
    assert result.results == []


async def test_delete_async(make_async_client: AsyncClientFactory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": "ok"})

    async with make_async_client(handler) as client:
        result = await client.queries.delete(query_id="q5")

    assert result is None


def test_save_results_posts_json_body(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"query_id": "q6", "action": "thin_discover", "row_count": 1})

    with make_client(handler) as client:
        result = client.queries.save_results(query_name="R", action="discover", data=[{"domain": "a.com"}], tags=["x"])

    assert seen["path"] == "/v1/queries/save-results"
    assert seen["method"] == "POST"
    assert seen["body"] == {"query_name": "R", "action": "discover", "data": [{"domain": "a.com"}], "tags": ["x"]}
    assert result.query_id == "q6"
    assert result.action == "thin_discover"
    assert result.row_count == 1


async def test_save_results_async(make_async_client: AsyncClientFactory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"query_id": "q7"})

    async with make_async_client(handler) as client:
        result = await client.queries.save_results(query_name="R", action="discover", data=[{"domain": "a.com"}])

    assert result.query_id == "q7"


def test_route_metadata_stamped() -> None:
    from discolike.resources._base import get_discolike_route
    from discolike.resources.queries import QueriesResource

    assert get_discolike_route(QueriesResource.list) == ("GET", "/queries/saved", True, ())
    assert get_discolike_route(QueriesResource.create_exclusion_list) == ("POST", "/queries/exclusion-list", True, ())
    assert get_discolike_route(QueriesResource.update) == ("PATCH", "/queries/{query_id}", True, ())
    assert get_discolike_route(QueriesResource.delete) == ("DELETE", "/queries/{query_id}", True, ())
    assert get_discolike_route(QueriesResource.save_results) == ("POST", "/queries/save-results", True, ())
