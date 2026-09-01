import httpx2
import pytest

from discolike import ValidationError
from discolike import async_signup
from discolike import signup
from discolike.signup import SignupResult

_RESPONSE = {
    "status": "created",
    "email": "jane@acme.com",
    "org_domain": "acme.com",
    "org_status": "created",
    "next_step": "A confirmation email was sent to jane@acme.com.",
}


def test_signup_posts_without_credentials() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("Authorization")
        seen["key"] = request.headers.get("x-discolike-key")
        seen["body"] = request.read()
        return httpx2.Response(201, json=_RESPONSE)

    client = httpx2.Client(base_url="https://api.test/v1", transport=httpx2.MockTransport(handler))
    result = signup(email="jane@acme.com", first_name="Jane", last_name="Doe", http_client=client)

    assert isinstance(result, SignupResult)
    assert result.org_status == "created"
    assert seen["path"] == "/v1/public/signup"
    assert seen["auth"] is None
    assert seen["key"] is None
    assert b'"agent": "discolike-python/' in seen["body"] or b'"agent":"discolike-python/' in seen["body"]


def test_signup_agent_override() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert b"my-agent" in request.read()
        return httpx2.Response(201, json=_RESPONSE)

    client = httpx2.Client(base_url="https://api.test/v1", transport=httpx2.MockTransport(handler))
    signup(email="jane@acme.com", first_name="Jane", last_name="Doe", agent="my-agent", http_client=client)


def test_signup_conflict_raises() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(409, json={"detail": "An account for this email already exists."})

    client = httpx2.Client(base_url="https://api.test/v1", transport=httpx2.MockTransport(handler))
    with pytest.raises(ValidationError, match="already exists"):
        signup(email="jane@acme.com", first_name="Jane", last_name="Doe", http_client=client)


async def test_async_signup() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(201, json=_RESPONSE)

    client = httpx2.AsyncClient(base_url="https://api.test/v1", transport=httpx2.MockTransport(handler))
    result = await async_signup(email="jane@acme.com", first_name="Jane", last_name="Doe", http_client=client)
    assert result.email == "jane@acme.com"
