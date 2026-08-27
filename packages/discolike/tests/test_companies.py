import httpx2
import pydantic
import pytest

from discolike.requests import CompaniesDataParams
from discolike.requests import CompaniesExtractParams
from discolike.requests import CompaniesGrowthParams
from discolike.requests import CompaniesPublicLinksParams
from discolike.requests import CompaniesRedirectsParams
from discolike.requests import CompaniesScoreParams
from discolike.requests import CompaniesSubsidiariesParams
from discolike.requests import CompaniesVendorsParams
from discolike_testkit import AsyncClientFactory
from discolike_testkit import ClientFactory

CASES = [
    ("data", CompaniesDataParams(domain="acme.com"), "/v1/bizdata"),
    ("score", CompaniesScoreParams(domain="acme.com"), "/v1/score"),
    ("growth", CompaniesGrowthParams(domain="acme.com"), "/v1/growth"),
    ("extract", CompaniesExtractParams(url="https://acme.com/about"), "/v1/extract"),
]

LIST_CASES = [
    ("redirects", CompaniesRedirectsParams(domain="acme.com"), "/v1/redirects"),
    ("vendors", CompaniesVendorsParams(domain="acme.com", match="vendor"), "/v1/vendors"),
    ("subsidiaries", CompaniesSubsidiariesParams(domain="acme.com"), "/v1/subsidiaries"),
    ("public_links", CompaniesPublicLinksParams(domain="acme.com", source="email"), "/v1/publiclink"),
]


@pytest.mark.parametrize(("method", "params", "path"), CASES)
def test_companies_methods(method: str, params, path: str, make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["params"] = dict(httpx2.QueryParams(request.url.query))
        return httpx2.Response(200, json={"domain": "acme.com", "anything": 1})

    with make_client(handler) as client:
        result = getattr(client.companies, method)(params)

    assert seen["path"] == path
    assert seen["params"] == {key: str(value) for key, value in params.to_wire().items()}
    assert result.model_extra["anything"] == 1


@pytest.mark.parametrize(("method", "params", "path"), CASES)
async def test_companies_methods_async(method: str, params, path: str, make_async_client: AsyncClientFactory) -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["params"] = dict(httpx2.QueryParams(request.url.query))
        return httpx2.Response(200, json={"domain": "acme.com", "anything": 1})

    async with make_async_client(handler) as client:
        result = await getattr(client.companies, method)(params)

    assert seen["path"] == path
    assert seen["params"] == {key: str(value) for key, value in params.to_wire().items()}
    assert result.model_extra["anything"] == 1


@pytest.mark.parametrize(("method", "params", "path"), LIST_CASES)
def test_companies_list_methods(method: str, params, path: str, make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["params"] = dict(httpx2.QueryParams(request.url.query))
        return httpx2.Response(200, json=[{"linked_domain": "acme.io", "anything": 1}])

    with make_client(handler) as client:
        result = getattr(client.companies, method)(params)

    assert seen["path"] == path
    assert seen["params"] == {key: str(value) for key, value in params.to_wire().items()}
    assert len(result) == 1
    assert result[0].linked_domain == "acme.io"
    assert result[0].model_extra["anything"] == 1


@pytest.mark.parametrize(("method", "params", "path"), LIST_CASES)
async def test_companies_list_methods_async(
    method: str, params, path: str, make_async_client: AsyncClientFactory
) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json=[{"linked_domain": "acme.io"}])

    async with make_async_client(handler) as client:
        result = await getattr(client.companies, method)(params)

    assert len(result) == 1
    assert result[0].linked_domain == "acme.io"


def test_extract_parses_text_and_language(make_client: ClientFactory) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"language": "en", "text": "Acme makes widgets."})

    with make_client(handler) as client:
        result = client.companies.extract(CompaniesExtractParams(domain="acme.com"))

    assert result.text == "Acme makes widgets."
    assert result.language == "en"


def test_unset_match_mode_is_not_sent(make_client: ClientFactory) -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["params"] = dict(httpx2.QueryParams(request.url.query))
        return httpx2.Response(200, json=[])

    with make_client(handler) as client:
        client.companies.redirects(CompaniesRedirectsParams(domain="acme.com"))

    assert seen["params"] == {"domain": "acme.com"}


def test_invalid_match_mode_fails_before_any_request() -> None:
    with pytest.raises(pydantic.ValidationError, match="match"):
        CompaniesRedirectsParams.model_validate({"domain": "acme.com", "match": "loose"})
