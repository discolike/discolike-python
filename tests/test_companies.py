import httpx
import pytest

from conftest import make_async_client, make_client

CASES = [
    ("data", {"domain": "acme.com"}, "/v1/bizdata"),
    ("score", {"domain": "acme.com"}, "/v1/score"),
    ("growth", {"domain": "acme.com"}, "/v1/growth"),
    ("metrics", {"domain": "acme.com"}, "/v1/metrics"),
    ("history", {"domain": "acme.com", "max_records": 100}, "/v1/history"),
    ("extract", {"url": "https://acme.com/about"}, "/v1/extract"),
    ("redirects", {"domain": "acme.com"}, "/v1/redirects"),
    ("vendors", {"domain": "acme.com"}, "/v1/vendors"),
    ("subsidiaries", {"domain": "acme.com"}, "/v1/subsidiaries"),
    ("public_links", {"domain": "acme.com", "source": "email"}, "/v1/publiclink"),
]


@pytest.mark.parametrize(("method", "kwargs", "path"), CASES)
def test_companies_methods(method: str, kwargs: dict, path: str) -> None:
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
async def test_companies_methods_async(method: str, kwargs: dict, path: str) -> None:
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
