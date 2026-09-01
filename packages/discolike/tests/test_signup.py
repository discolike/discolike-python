import httpx2
import pytest

from discolike import DiscolikeError
from discolike import ValidationError
from discolike import async_signup
from discolike import signup
from discolike._config import load_signup_email
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


def test_signup_remembers_email() -> None:
    client = httpx2.Client(
        base_url="https://api.test/v1",
        transport=httpx2.MockTransport(lambda request: httpx2.Response(201, json=_RESPONSE)),
    )
    signup(email="jane@acme.com", first_name="Jane", last_name="Doe", http_client=client)
    assert load_signup_email() == "jane@acme.com"


def test_signup_different_email_rejected_without_http_call() -> None:
    client = httpx2.Client(
        base_url="https://api.test/v1",
        transport=httpx2.MockTransport(lambda request: httpx2.Response(201, json=_RESPONSE)),
    )
    signup(email="jane@acme.com", first_name="Jane", last_name="Doe", http_client=client)

    def unexpected_call(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("HTTP request should not have been made")

    blocked_client = httpx2.Client(base_url="https://api.test/v1", transport=httpx2.MockTransport(unexpected_call))
    with pytest.raises(DiscolikeError, match=r"jane@acme\.com"):
        signup(email="other@acme.com", first_name="Other", last_name="Person", http_client=blocked_client)


def test_signup_same_email_again_succeeds() -> None:
    client = httpx2.Client(
        base_url="https://api.test/v1",
        transport=httpx2.MockTransport(lambda request: httpx2.Response(201, json=_RESPONSE)),
    )
    signup(email="jane@acme.com", first_name="Jane", last_name="Doe", http_client=client)
    result = signup(email="Jane@Acme.com", first_name="Jane", last_name="Doe", http_client=client)
    assert result.email == "jane@acme.com"


def test_signup_allow_new_email_updates_stored_email() -> None:
    client = httpx2.Client(
        base_url="https://api.test/v1",
        transport=httpx2.MockTransport(lambda request: httpx2.Response(201, json=_RESPONSE)),
    )
    signup(email="jane@acme.com", first_name="Jane", last_name="Doe", http_client=client)

    other_response = {**_RESPONSE, "email": "other@acme.com"}
    other_client = httpx2.Client(
        base_url="https://api.test/v1",
        transport=httpx2.MockTransport(lambda request: httpx2.Response(201, json=other_response)),
    )
    result = signup(
        email="other@acme.com", first_name="Other", last_name="Person", http_client=other_client, allow_new_email=True
    )
    assert result.email == "other@acme.com"
    assert load_signup_email() == "other@acme.com"
