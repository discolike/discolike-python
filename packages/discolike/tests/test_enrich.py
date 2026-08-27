from __future__ import annotations

import io

import httpx2
import pytest

from discolike._jobs import FAMILY_SEGMENT
from discolike._jobs import AsyncJob
from discolike._jobs import Job
from discolike_testkit import AsyncClientFactory
from discolike_testkit import ClientFactory


def test_append_json_response_parses_result_list(make_client: ClientFactory) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/v1/append"
        params = dict(httpx2.QueryParams(request.url.query))
        assert params["domain_column"] == "website"
        assert b"Acme" in request.content
        return httpx2.Response(200, json=[{"domain": "acme.com", "name": "Acme", "extra_field": "kept"}])

    with make_client(handler) as client:
        result = client._enrich.append(file=io.BytesIO(b"website\nAcme\n"), domain_column="website")

    assert isinstance(result, list)
    assert result[0].domain == "acme.com"
    assert result[0].model_extra["extra_field"] == "kept"  # ty: ignore[not-subscriptable]


def test_append_csv_response_returns_raw_bytes(make_client: ClientFactory) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, content=b"col1,col2\n", headers={"Content-Type": "text/csv"})

    with make_client(handler) as client:
        result = client.append(file=io.BytesIO(b"domain\nacme.com\n"), csv=True)

    assert result == b"col1,col2\n"


def test_append_sends_dataset_query_params(tmp_path, make_client: ClientFactory) -> None:
    csv_path = tmp_path / "domains.csv"
    csv_path.write_text("domain\nacme.com\n")
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["params"] = httpx2.QueryParams(request.url.query)
        return httpx2.Response(200, json=[])

    with make_client(handler) as client:
        client.append(file=csv_path, dataset=["bizdata", "growth"])

    assert seen["params"].get_list("dataset") == ["bizdata", "growth"]


async def test_append_async_json_response(make_async_client: AsyncClientFactory) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json=[{"domain": "acme.com"}])

    async with make_async_client(handler) as client:
        result = await client.append(file=io.BytesIO(b"domain\nacme.com\n"))

    assert isinstance(result, list)
    assert result[0].domain == "acme.com"


def test_segment_domains_branch_comma_joins_and_returns_job(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["params"] = httpx2.QueryParams(request.url.query)
        return httpx2.Response(200, json={"task_id": "seg-1"})

    with make_client(handler) as client:
        job = client.segment(domains=["acme.com", "beta.com"], max_segments=5)

    assert seen["path"] == "/v1/segment"
    assert seen["params"]["domains"] == "acme.com,beta.com"
    assert seen["params"]["max_segments"] == "5"
    assert isinstance(job, Job)
    assert job.task_family == FAMILY_SEGMENT
    assert job.task_id == "seg-1"


def test_segment_file_branch_returns_job(tmp_path, make_client: ClientFactory) -> None:
    csv_path = tmp_path / "domains.csv"
    csv_path.write_text("domain\nacme.com\n")
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        seen["content"] = request.content
        return httpx2.Response(200, json={"task_id": "seg-2"})

    with make_client(handler) as client:
        job = client.segment(file=csv_path, domain_column="domain")

    assert seen["path"] == "/v1/segment"
    assert seen["method"] == "POST"
    assert b"acme.com" in seen["content"]
    assert isinstance(job, Job)
    assert job.task_id == "seg-2"


def test_segment_raises_when_neither_domains_nor_file_given(make_client: ClientFactory) -> None:
    with (
        make_client(lambda request: httpx2.Response(200, json={})) as client,
        pytest.raises(ValueError, match="one of domains, query_id, or file is required"),
    ):
        client.segment()


def test_segment_raises_when_both_domains_and_file_given(tmp_path, make_client: ClientFactory) -> None:
    csv_path = tmp_path / "domains.csv"
    csv_path.write_text("domain\nacme.com\n")

    with (
        make_client(lambda request: httpx2.Response(200, json={})) as client,
        pytest.raises(ValueError, match="file cannot be combined with domains or query_id"),
    ):
        client.segment(domains=["acme.com"], file=csv_path)


def test_segment_raises_when_domain_column_given_with_domains(make_client: ClientFactory) -> None:
    with (
        make_client(lambda request: httpx2.Response(200, json={})) as client,
        pytest.raises(ValueError, match="domain_column only applies to file uploads"),
    ):
        client.segment(domains=["acme.com"], domain_column="domain")


async def test_segment_async_domains_branch(make_async_client: AsyncClientFactory) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"task_id": "seg-3"})

    async with make_async_client(handler) as client:
        job = await client.segment(domains=["acme.com"])

    assert isinstance(job, AsyncJob)
    assert job.task_id == "seg-3"


def test_route_metadata_stamped() -> None:
    from discolike.resources._base import get_discolike_route
    from discolike.resources.enrich import EnrichResource

    assert get_discolike_route(EnrichResource.append) == ("POST", "/append", True)
    assert get_discolike_route(EnrichResource.segment) == ("GET", "/segment", True)
    assert get_discolike_route(EnrichResource._segment_file) == ("POST", "/segment", True)
