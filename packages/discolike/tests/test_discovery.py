from __future__ import annotations

import httpx2

from discolike_testkit import AsyncClientFactory
from discolike_testkit import ClientFactory


def test_discover_builds_query_and_parses_list(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["params"] = httpx2.QueryParams(request.url.query)
        return httpx2.Response(
            200,
            json=[{"domain": "acme.com", "name": "Acme", "similarity": 87.3, "extra_field": "kept"}],
        )

    with make_client(handler) as client:
        results = client.discover(icp_prompt="B2B fintech in DE", country=["DE", "AT"], max_records=50)

    assert seen["path"] == "/v1/discover"
    assert seen["params"].get_list("country") == ["DE", "AT"]
    assert seen["params"]["max_records"] == "50"
    assert "domain" not in dict(seen["params"])
    assert results[0].domain == "acme.com"
    assert results[0].similarity == 87.3
    assert results[0].model_extra["extra_field"] == "kept"  # ty: ignore[not-subscriptable]


def test_count(make_client: ClientFactory) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/v1/count"
        return httpx2.Response(200, json={"count": 1234})

    with make_client(handler) as client:
        result = client.count(category=["CYBERSECURITY"])
    assert result.count == 1234


async def test_discover_async(make_async_client: AsyncClientFactory) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json=[{"domain": "a.com"}])

    async with make_async_client(handler) as client:
        results = await client.discover(domain=["stripe.com"])
    assert results[0].domain == "a.com"
