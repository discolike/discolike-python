from __future__ import annotations

import io

import httpx2
import pydantic
import pytest

from discolike._jobs import FAMILY_SEGMENT
from discolike._jobs import AsyncJob
from discolike._jobs import Job
from discolike.requests import AppendParams
from discolike.requests import SegmentFileParams
from discolike.requests import SegmentParams
from discolike_testkit import AsyncClientFactory
from discolike_testkit import ClientFactory


def test_append_json_response_parses_result_list(make_client: ClientFactory) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/v1/append"
        params = httpx2.QueryParams(request.url.query)
        assert params["domain_column"] == "website"
        assert params.get_list("dataset") == ["bizdata"]
        assert b"Acme" in request.content
        return httpx2.Response(200, json=[{"domain": "acme.com", "name": "Acme", "extra_field": "kept"}])

    with make_client(handler) as client:
        result = client._enrich.append(
            AppendParams(dataset=["bizdata"], domain_column="website"), file=io.BytesIO(b"website\nAcme\n")
        )

    assert isinstance(result, list)
    assert result[0].domain == "acme.com"
    assert result[0].model_extra["extra_field"] == "kept"  # ty: ignore[not-subscriptable]


def test_append_csv_response_returns_raw_bytes(make_client: ClientFactory) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, content=b"col1,col2\n", headers={"Content-Type": "text/csv"})

    with make_client(handler) as client:
        result = client.append(AppendParams(dataset=["bizdata"], csv=True), file=io.BytesIO(b"domain\nacme.com\n"))

    assert result == b"col1,col2\n"


def test_append_sends_dataset_query_params(tmp_path, make_client: ClientFactory) -> None:
    csv_path = tmp_path / "domains.csv"
    csv_path.write_text("domain\nacme.com\n")
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["params"] = httpx2.QueryParams(request.url.query)
        return httpx2.Response(200, json=[])

    with make_client(handler) as client:
        client.append(AppendParams(dataset=["bizdata", "growth"]), file=csv_path)

    assert seen["params"].get_list("dataset") == ["bizdata", "growth"]


def test_append_without_file_uses_query_id_only(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["params"] = httpx2.QueryParams(request.url.query)
        seen["content"] = request.content
        return httpx2.Response(200, json=[])

    with make_client(handler) as client:
        client.append(AppendParams(dataset=["bizdata"], query_id=["q1"]))

    assert seen["params"]["query_id"] == "q1"
    assert seen["content"] == b""


def test_append_raises_when_neither_file_nor_query_id_given(make_client: ClientFactory) -> None:
    with (
        make_client(lambda request: httpx2.Response(200, json=[])) as client,
        pytest.raises(ValueError, match="one of file or query_id is required"),
    ):
        client.append(AppendParams(dataset=["bizdata"]))


def test_append_rejects_unknown_dataset_before_any_request() -> None:
    with pytest.raises(pydantic.ValidationError, match="dataset"):
        AppendParams.model_validate({"dataset": ["bogus"]})


async def test_append_async_json_response(make_async_client: AsyncClientFactory) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json=[{"domain": "acme.com"}])

    async with make_async_client(handler) as client:
        result = await client.append(AppendParams(dataset=["bizdata"]), file=io.BytesIO(b"domain\nacme.com\n"))

    assert isinstance(result, list)
    assert result[0].domain == "acme.com"


def test_segment_sends_comma_separated_domains_and_returns_job(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        seen["params"] = httpx2.QueryParams(request.url.query)
        return httpx2.Response(200, json={"task_id": "seg-1"})

    with make_client(handler) as client:
        job = client.segment(SegmentParams(domains="acme.com,beta.com", max_segments=5))

    assert seen["path"] == "/v1/segment"
    assert seen["method"] == "GET"
    assert seen["params"]["domains"] == "acme.com,beta.com"
    assert seen["params"]["max_segments"] == "5"
    assert isinstance(job, Job)
    assert job.task_family == FAMILY_SEGMENT
    assert job.task_id == "seg-1"


def test_segment_file_posts_upload_and_returns_job(tmp_path, make_client: ClientFactory) -> None:
    csv_path = tmp_path / "domains.csv"
    csv_path.write_text("domain\nacme.com\n")
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        seen["params"] = httpx2.QueryParams(request.url.query)
        seen["content"] = request.content
        return httpx2.Response(200, json={"task_id": "seg-2"})

    with make_client(handler) as client:
        job = client.segment_file(SegmentFileParams(domain_column="domain"), file=csv_path)

    assert seen["path"] == "/v1/segment"
    assert seen["method"] == "POST"
    assert seen["params"]["domain_column"] == "domain"
    assert b"acme.com" in seen["content"]
    assert isinstance(job, Job)
    assert job.task_id == "seg-2"


def test_segment_raises_when_neither_domains_nor_query_id_given(make_client: ClientFactory) -> None:
    with (
        make_client(lambda request: httpx2.Response(200, json={})) as client,
        pytest.raises(ValueError, match="one of domains or query_id is required"),
    ):
        client.segment(SegmentParams())


def test_segment_rejects_max_segments_out_of_range_before_any_request() -> None:
    with pytest.raises(pydantic.ValidationError, match="max_segments"):
        SegmentParams(domains="acme.com", max_segments=99)


async def test_segment_async(make_async_client: AsyncClientFactory) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"task_id": "seg-3"})

    async with make_async_client(handler) as client:
        job = await client.segment(SegmentParams(domains="acme.com"))

    assert isinstance(job, AsyncJob)
    assert job.task_id == "seg-3"


async def test_segment_file_async(tmp_path, make_async_client: AsyncClientFactory) -> None:
    csv_path = tmp_path / "domains.csv"
    csv_path.write_text("domain\nacme.com\n")

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.method == "POST"
        return httpx2.Response(200, json={"task_id": "seg-4"})

    async with make_async_client(handler) as client:
        job = await client.segment_file(SegmentFileParams(), file=csv_path)

    assert isinstance(job, AsyncJob)
    assert job.task_id == "seg-4"


def test_route_metadata_stamped() -> None:
    from discolike.resources._base import get_discolike_route
    from discolike.resources.enrich import EnrichResource

    assert get_discolike_route(EnrichResource.append) == ("POST", "/append", True)
    assert get_discolike_route(EnrichResource.segment) == ("GET", "/segment", True)
    assert get_discolike_route(EnrichResource.segment_file) == ("POST", "/segment", True)
