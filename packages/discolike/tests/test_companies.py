import httpx
import pytest

from discolike_testkit import AsyncClientFactory
from discolike_testkit import ClientFactory

CASES = [
    ("data", {"domain": "acme.com"}, "/v1/bizdata"),
    ("score", {"domain": "acme.com"}, "/v1/score"),
    ("growth", {"domain": "acme.com"}, "/v1/growth"),
    ("extract", {"url": "https://acme.com/about"}, "/v1/extract"),
]

LIST_CASES = [
    ("redirects", {"domain": "acme.com"}, "/v1/redirects"),
    ("vendors", {"domain": "acme.com"}, "/v1/vendors"),
    ("subsidiaries", {"domain": "acme.com"}, "/v1/subsidiaries"),
    ("public_links", {"domain": "acme.com", "source": "email"}, "/v1/publiclink"),
]


@pytest.mark.parametrize(("method", "kwargs", "path"), CASES)
def test_companies_methods(method: str, kwargs: dict, path: str, make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["params"] = dict(httpx.QueryParams(request.url.query))
        return httpx.Response(200, json={"domain": "acme.com", "anything": 1})

    with make_client(handler) as client:
        result = getattr(client.companies, method)(**kwargs)

    assert seen["path"] == path
    for key, value in kwargs.items():
        assert seen["params"][key] == str(value)
    assert result.model_extra["anything"] == 1


@pytest.mark.parametrize(("method", "kwargs", "path"), CASES)
async def test_companies_methods_async(
    method: str, kwargs: dict, path: str, make_async_client: AsyncClientFactory
) -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["params"] = dict(httpx.QueryParams(request.url.query))
        return httpx.Response(200, json={"domain": "acme.com", "anything": 1})

    async with make_async_client(handler) as client:
        result = await getattr(client.companies, method)(**kwargs)

    assert seen["path"] == path
    for key, value in kwargs.items():
        assert seen["params"][key] == str(value)
    assert result.model_extra["anything"] == 1


@pytest.mark.parametrize(("method", "kwargs", "path"), LIST_CASES)
def test_companies_list_methods(method: str, kwargs: dict, path: str, make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["params"] = dict(httpx.QueryParams(request.url.query))
        return httpx.Response(200, json=[{"linked_domain": "acme.io", "anything": 1}])

    with make_client(handler) as client:
        result = getattr(client.companies, method)(**kwargs)

    assert seen["path"] == path
    for key, value in kwargs.items():
        assert seen["params"][key] == str(value)
    assert len(result) == 1
    assert result[0].linked_domain == "acme.io"
    assert result[0].model_extra["anything"] == 1


@pytest.mark.parametrize(("method", "kwargs", "path"), LIST_CASES)
async def test_companies_list_methods_async(
    method: str, kwargs: dict, path: str, make_async_client: AsyncClientFactory
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"linked_domain": "acme.io"}])

    async with make_async_client(handler) as client:
        result = await getattr(client.companies, method)(**kwargs)

    assert len(result) == 1
    assert result[0].linked_domain == "acme.io"


def test_extract_parses_text_and_language(make_client: ClientFactory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"language": "en", "text": "Acme makes widgets."})

    with make_client(handler) as client:
        result = client.companies.extract(domain="acme.com")

    assert result.text == "Acme makes widgets."
    assert result.language == "en"
