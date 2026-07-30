from __future__ import annotations

import json

import httpx
import pytest

from discolike._jobs import FAMILY_DISCOGEN
from discolike._jobs import AsyncJob
from discolike._jobs import Job
from discolike_testkit import AsyncClientFactory
from discolike_testkit import ClientFactory


def test_process_posts_json_and_returns_job(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"task_id": "dg-1"})

    with make_client(handler) as client:
        job = client.discogen.process(
            query="Recent funding rounds",
            domains=["acme.com", "globex.com"],
            web_search=True,
        )

    assert seen["path"] == "/v1/discogen/process"
    assert seen["method"] == "POST"
    assert seen["body"] == {
        "query": "Recent funding rounds",
        "domains": ["acme.com", "globex.com"],
        "web_search": True,
    }
    assert isinstance(job, Job)
    assert job.task_family == FAMILY_DISCOGEN
    assert job.task_id == "dg-1"


def test_process_drops_unset_optionals(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"task_id": "dg-2"})

    with make_client(handler) as client:
        client.discogen.process(query="q", domains=["a.com"])

    assert seen["body"] == {"query": "q", "domains": ["a.com"]}


def test_process_all_optionals_present(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"task_id": "dg-3"})

    with make_client(handler) as client:
        client.discogen.process(
            query="q",
            domains=["a.com"],
            integration_id="int-1",
            web_search=True,
            context_mode="website",
            include_x_search=False,
            search_provider_id="serper",
            search_context_size="medium",
        )

    assert seen["body"] == {
        "query": "q",
        "domains": ["a.com"],
        "integration_id": "int-1",
        "web_search": True,
        "context_mode": "website",
        "include_x_search": False,
        "search_provider_id": "serper",
        "search_context_size": "medium",
    }


def test_process_personas_posts_json_and_returns_job(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"task_id": "dg-4"})

    with make_client(handler) as client:
        job = client.discogen.process_personas(
            query="Recent job changes",
            persona_ids=[111, 222],
        )

    assert seen["path"] == "/v1/discogen/process-personas"
    assert seen["method"] == "POST"
    assert seen["body"] == {"query": "Recent job changes", "persona_ids": [111, 222]}
    assert isinstance(job, Job)
    assert job.task_family == FAMILY_DISCOGEN
    assert job.task_id == "dg-4"


def test_models(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        return httpx.Response(200, json={"models": ["grok-4", "gpt-5.4"]})

    with make_client(handler) as client:
        result = client.discogen.models()

    assert seen["path"] == "/v1/discogen/models"
    assert seen["method"] == "GET"
    assert result.model_extra["models"] == ["grok-4", "gpt-5.4"]  # ty: ignore[not-subscriptable]


def test_job_reattaches_without_http_call(make_client: ClientFactory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("job() must not perform an HTTP request")

    with make_client(handler) as client:
        job = client.discogen.job("dg-existing")

    assert isinstance(job, Job)
    assert job.task_family == FAMILY_DISCOGEN
    assert job.task_id == "dg-existing"


def test_validate_icp_posts_json_and_returns_job(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"task_id": "val-1"})

    with make_client(handler) as client:
        job = client.validate_icp(
            icp_text="VPs of Marketing at B2B SaaS",
            domains=["gusto.com", "rippling.com"],
        )

    assert seen["path"] == "/v1/validate/icp"
    assert seen["method"] == "POST"
    assert seen["body"] == {
        "icp_text": "VPs of Marketing at B2B SaaS",
        "domains": ["gusto.com", "rippling.com"],
    }
    assert isinstance(job, Job)
    assert job.task_family == FAMILY_DISCOGEN
    assert job.task_id == "val-1"


def test_validate_icp_all_optionals_present(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"task_id": "val-2"})

    with make_client(handler) as client:
        client.validate_icp(
            icp_text="q",
            domains=["a.com"],
            context_mode="website",
            integration_id="int-1",
            web_search=True,
            search_provider_id="serper",
        )

    assert seen["body"] == {
        "icp_text": "q",
        "domains": ["a.com"],
        "context_mode": "website",
        "integration_id": "int-1",
        "web_search": True,
        "search_provider_id": "serper",
    }


async def test_process_async_returns_async_job(make_async_client: AsyncClientFactory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"task_id": "dg-async-1"})

    async with make_async_client(handler) as client:
        job = await client.discogen.process(query="q", domains=["a.com"])

    assert isinstance(job, AsyncJob)
    assert job.task_family == FAMILY_DISCOGEN
    assert job.task_id == "dg-async-1"


async def test_process_personas_async_returns_async_job(make_async_client: AsyncClientFactory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"task_id": "dg-async-2"})

    async with make_async_client(handler) as client:
        job = await client.discogen.process_personas(query="q", persona_ids=[1])

    assert isinstance(job, AsyncJob)
    assert job.task_family == FAMILY_DISCOGEN
    assert job.task_id == "dg-async-2"


async def test_models_async(make_async_client: AsyncClientFactory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": ["grok-4"]})

    async with make_async_client(handler) as client:
        result = await client.discogen.models()

    assert result.model_extra["models"] == ["grok-4"]  # ty: ignore[not-subscriptable]


async def test_job_async_reattaches_without_http_call(make_async_client: AsyncClientFactory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("job() must not perform an HTTP request")

    async with make_async_client(handler) as client:
        job = client.discogen.job("dg-existing-async")

    assert isinstance(job, AsyncJob)
    assert job.task_family == FAMILY_DISCOGEN
    assert job.task_id == "dg-existing-async"


async def test_validate_icp_async_returns_async_job(make_async_client: AsyncClientFactory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"task_id": "val-async-1"})

    async with make_async_client(handler) as client:
        job = await client.validate_icp(icp_text="q", domains=["a.com"])

    assert isinstance(job, AsyncJob)
    assert job.task_family == FAMILY_DISCOGEN
    assert job.task_id == "val-async-1"


def test_route_metadata_stamped() -> None:
    from discolike.resources._base import get_discolike_route
    from discolike.resources.discogen import DiscogenResource
    from discolike.resources.discogen import ValidateResource

    assert get_discolike_route(DiscogenResource.process) == ("POST", "/discogen/process", True, ())
    assert get_discolike_route(DiscogenResource.process_personas) == ("POST", "/discogen/process-personas", True, ())
    assert get_discolike_route(DiscogenResource.models) == ("GET", "/discogen/models", True, ())
    assert get_discolike_route(DiscogenResource.job) is None
    assert get_discolike_route(ValidateResource.icp) == ("POST", "/validate/icp", True, ())
