import io

import httpx2
import pydantic
import pytest

from discolike._jobs import FAMILY_BULKMATCH
from discolike._jobs import AsyncJob
from discolike._jobs import Job
from discolike.requests import MatchBulkParams
from discolike.requests import MatchCompanyParams
from discolike_testkit import AsyncClientFactory
from discolike_testkit import ClientFactory


def test_company_sends_params_and_parses_response(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["params"] = dict(httpx2.QueryParams(request.url.query))
        return httpx2.Response(200, json={"domain": "acme.com", "anything": 1})

    with make_client(handler) as client:
        result = client.match.company(
            MatchCompanyParams(name="Acme Inc", city="Austin", strict=True, min_match_confidence=80)
        )

    assert seen["path"] == "/v1/match"
    assert seen["params"] == {"name": "Acme Inc", "city": "Austin", "strict": "true", "min_match_confidence": "80"}
    assert result.model_extra["anything"] == 1  # ty: ignore[not-subscriptable]


def test_company_omits_everything_not_set(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["params"] = dict(httpx2.QueryParams(request.url.query))
        return httpx2.Response(200, json={"domain": "acme.com"})

    with make_client(handler) as client:
        client.match.company(MatchCompanyParams(name="Acme Inc"))

    assert seen["params"] == {"name": "Acme Inc"}


def test_company_rejects_out_of_range_confidence_before_any_request() -> None:
    with pytest.raises(pydantic.ValidationError, match="min_match_confidence"):
        MatchCompanyParams(name="Acme Inc", min_match_confidence=10)


def test_bulk_posts_multipart_with_path(tmp_path, make_client: ClientFactory) -> None:
    csv_path = tmp_path / "companies.csv"
    csv_path.write_text("company\nAcme\n")
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["params"] = dict(httpx2.QueryParams(request.url.query))
        seen["content"] = request.content
        return httpx2.Response(200, json={"task_id": "bm-1"})

    with make_client(handler) as client:
        job = client.match.bulk(MatchBulkParams(name_column="company", min_match_confidence=80), file=csv_path)

    assert seen["path"] == "/v1/bulkmatch"
    assert seen["params"] == {"name_column": "company", "min_match_confidence": "80"}
    assert b"Acme" in seen["content"]
    assert isinstance(job, Job)
    assert job.task_family == FAMILY_BULKMATCH
    assert job.task_id == "bm-1"


def test_bulk_accepts_open_handle_without_closing_it(make_client: ClientFactory) -> None:
    handle = io.BytesIO(b"company\nAcme\n")
    handle.name = "companies.csv"

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"task_id": "bm-2"})

    with make_client(handler) as client:
        job = client.match.bulk(MatchBulkParams(name_column="company"), file=handle)

    assert job.task_id == "bm-2"
    assert handle.closed is False


async def test_async_company(make_async_client: AsyncClientFactory) -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["params"] = dict(httpx2.QueryParams(request.url.query))
        return httpx2.Response(200, json={"matches": []})

    async with make_async_client(handler) as client:
        result = await client.match.company(MatchCompanyParams(name="Acme Inc", local_mode=True))

    assert seen["params"] == {"name": "Acme Inc", "local_mode": "true"}
    assert result.matches == []


async def test_async_bulk_posts_multipart(tmp_path, make_async_client: AsyncClientFactory) -> None:
    csv_path = tmp_path / "companies.csv"
    csv_path.write_text("company\nAcme\n")
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["params"] = dict(httpx2.QueryParams(request.url.query))
        seen["content"] = request.content
        return httpx2.Response(200, json={"task_id": "bm-3"})

    async with make_async_client(handler) as client:
        job = await client.match.bulk(MatchBulkParams(name_column="company"), file=csv_path)

    assert seen["path"] == "/v1/bulkmatch"
    assert seen["params"] == {"name_column": "company"}
    assert b"Acme" in seen["content"]
    assert isinstance(job, AsyncJob)
    assert job.task_family == FAMILY_BULKMATCH
    assert job.task_id == "bm-3"
