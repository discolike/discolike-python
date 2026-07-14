from __future__ import annotations

import json

import httpx

from conftest import make_async_client
from conftest import make_client
from discolike._jobs import FAMILY_CONTACTMATCH
from discolike._jobs import FAMILY_DISCOGEN
from discolike._jobs import AsyncJob
from discolike._jobs import Job


def test_search_builds_query_and_parses_list() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        seen["params"] = httpx.QueryParams(request.url.query)
        return httpx.Response(
            200,
            json=[{"persona_id": 1, "domain": "acme.com", "name": "Jane Doe", "extra_field": "kept"}],
        )

    with make_client(handler) as client:
        results = client.contacts.search(seniority=["vp", "director"], domain=["acme.com"], max_records=25)

    assert seen["path"] == "/v1/contacts"
    assert seen["method"] == "GET"
    assert seen["params"].get_list("seniority") == ["vp", "director"]
    assert seen["params"]["domain"] == "acme.com"
    assert seen["params"]["max_records"] == "25"
    assert results[0].persona_id == 1
    assert results[0].model_extra["extra_field"] == "kept"  # ty: ignore[not-subscriptable]


def test_count() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        seen["params"] = httpx.QueryParams(request.url.query)
        return httpx.Response(200, json={"count": 1234})

    with make_client(handler) as client:
        result = client.contacts.count(seniority=["vp"], has_email=True)

    assert seen["path"] == "/v1/contacts/count"
    assert seen["method"] == "GET"
    assert seen["params"]["seniority"] == "vp"
    assert seen["params"]["has_email"] == "true"
    assert result.model_extra["count"] == 1234  # ty: ignore[not-subscriptable]


def test_lookup() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["params"] = httpx.QueryParams(request.url.query)
        return httpx.Response(
            200,
            json={"persona_id": 12345678, "name": "Jane Doe", "domain": "example.com"},
        )

    with make_client(handler) as client:
        result = client.contacts.lookup(persona_id=12345678, email="jane@example.com")

    assert seen["path"] == "/v1/contacts/lookup"
    assert seen["params"]["persona_id"] == "12345678"
    assert seen["params"]["email"] == "jane@example.com"
    assert result.persona_id == 12345678
    assert result.name == "Jane Doe"


def test_match() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["params"] = httpx.QueryParams(request.url.query)
        return httpx.Response(
            200,
            json={
                "query": {"name": "Jane Doe", "company_name": "Acme Corp", "domain": None},
                "matches": [
                    {
                        "persona_id": 12345678,
                        "name": "Jane Doe",
                        "title": "VP of Sales",
                        "domain": "acmecorp.com",
                        "company_name": "Acme Corporation",
                        "match_score": 95.2,
                    }
                ],
            },
        )

    with make_client(handler) as client:
        result = client.contacts.match(name="Jane Doe", company_name="Acme Corp", limit=5)

    assert seen["path"] == "/v1/contacts/match"
    assert seen["params"]["name"] == "Jane Doe"
    assert seen["params"]["limit"] == "5"
    assert result.query is not None
    assert result.query.name == "Jane Doe"
    assert result.matches[0].match_score == 95.2


def test_bulk_match_posts_json_and_returns_job() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"task_id": "cm-1"})

    with make_client(handler) as client:
        job = client.contacts.bulk_match(
            queries=[{"name": "Jane Doe", "company_name": "Acme Corp"}],
            enrich=True,
            limit=5,
        )

    assert seen["path"] == "/v1/contacts/bulk-match"
    assert seen["method"] == "POST"
    assert seen["body"] == {
        "queries": [{"name": "Jane Doe", "company_name": "Acme Corp"}],
        "enrich": True,
        "limit": 5,
    }
    assert isinstance(job, Job)
    assert job.task_family == FAMILY_CONTACTMATCH
    assert job.task_id == "cm-1"


def test_discover_posts_json_body() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "results": {"acme.com": {"domain": "acme.com", "contacts": []}},
                "total_contacts": 0,
                "total_domains": 1,
            },
        )

    with make_client(handler) as client:
        result = client.contacts.discover(domain=["acme.com"], seniority=["vp"], results_by_company=10, consensus=2)

    assert seen["path"] == "/v1/contacts/discover"
    assert seen["method"] == "POST"
    assert seen["body"] == {
        "domain": ["acme.com"],
        "seniority": ["vp"],
        "results_by_company": 10,
        "consensus": 2,
    }
    assert result.model_extra["total_domains"] == 1  # ty: ignore[not-subscriptable]


def test_generate_posts_json_and_returns_job() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"task_id": "dg-1"})

    with make_client(handler) as client:
        job = client.contacts.generate(
            icp_text="VPs of Marketing at B2B SaaS",
            domains=["gusto.com", "rippling.com"],
            context_mode="website",
        )

    assert seen["path"] == "/v1/contacts/discover/generate"
    assert seen["method"] == "POST"
    assert seen["body"] == {
        "icp_text": "VPs of Marketing at B2B SaaS",
        "domains": ["gusto.com", "rippling.com"],
        "context_mode": "website",
    }
    assert isinstance(job, Job)
    assert job.task_family == FAMILY_DISCOGEN
    assert job.task_id == "dg-1"


async def test_search_async() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"persona_id": 2, "domain": "b.com"}])

    async with make_async_client(handler) as client:
        results = await client.contacts.search(domain=["b.com"])
    assert results[0].persona_id == 2


async def test_bulk_match_async_returns_async_job() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"task_id": "cm-2"})

    async with make_async_client(handler) as client:
        job = await client.contacts.bulk_match(queries=[{"name": "Jane Doe"}])

    assert isinstance(job, AsyncJob)
    assert job.task_family == FAMILY_CONTACTMATCH
    assert job.task_id == "cm-2"


async def test_generate_async_returns_async_job() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"task_id": "dg-2"})

    async with make_async_client(handler) as client:
        job = await client.contacts.generate(icp_text="VPs", domains=["a.com"])

    assert isinstance(job, AsyncJob)
    assert job.task_family == FAMILY_DISCOGEN
    assert job.task_id == "dg-2"


def test_route_metadata_stamped() -> None:
    from discolike.resources._base import get_discolike_route
    from discolike.resources.contacts import ContactsResource

    assert get_discolike_route(ContactsResource.search) == ("GET", "/contacts", False, ())
    assert get_discolike_route(ContactsResource.count) == ("GET", "/contacts/count", False, ())
    assert get_discolike_route(ContactsResource.lookup) == ("GET", "/contacts/lookup", False, ())
    assert get_discolike_route(ContactsResource.match) == ("GET", "/contacts/match", False, ())
    assert get_discolike_route(ContactsResource.bulk_match) == ("POST", "/contacts/bulk-match", False, ())
    assert get_discolike_route(ContactsResource.discover) == ("POST", "/contacts/discover", True, ())
    assert get_discolike_route(ContactsResource.generate) == ("POST", "/contacts/discover/generate", True, ())
