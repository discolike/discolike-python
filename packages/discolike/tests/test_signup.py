import httpx2
import pytest

from discolike import DiscolikeError
from discolike import ValidationError
from discolike import async_signup
from discolike import signup
from discolike._config import load_signup_email
from discolike.signup import MAX_NAME_LENGTH
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


@pytest.mark.parametrize(
    "name",
    [
        "Jane",
        "Mary-Jane",
        "O'Brien",
        "O\u2019Brien",
        "St. John",
        "José",
        "Zoë",
        "李",
        "Jean Luc",
        "J",
        "x" * MAX_NAME_LENGTH,
        "Jane2",
        "Anne (AM)",
        "J.R., Jr",
        "Jane_Doe",
        "jane@acme.com",
        "Björn 2nd",
    ],
)
def test_accepted_names(name: str) -> None:
    client = httpx2.Client(
        base_url="https://api.test/v1",
        transport=httpx2.MockTransport(lambda request: httpx2.Response(201, json=_RESPONSE)),
    )
    result = signup(email="jane@acme.com", first_name=name, last_name=name, http_client=client)
    assert isinstance(result, SignupResult)


@pytest.mark.parametrize(
    "name",
    [
        "Jane<b>",
        "\U0001f600",
        "-",
        "123",
        "Jane​",
        "Jane\x07",
        "",
        " ",
        "   ",
        "x" * (MAX_NAME_LENGTH + 1),
    ],
)
def test_rejected_names(name: str) -> None:
    def unexpected_call(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("HTTP request should not have been made")

    client = httpx2.Client(base_url="https://api.test/v1", transport=httpx2.MockTransport(unexpected_call))
    with pytest.raises(ValidationError):
        signup(email="jane@acme.com", first_name=name, last_name="Doe", http_client=client)


def test_charset_rejection_names_the_rule() -> None:
    client = httpx2.Client(
        base_url="https://api.test/v1", transport=httpx2.MockTransport(lambda r: httpx2.Response(201))
    )
    with pytest.raises(ValidationError, match="must contain a letter and no angle brackets or control characters"):
        signup(email="jane@acme.com", first_name="Jane<b>", last_name="Doe", http_client=client)


def test_over_length_rejection_names_the_limit() -> None:
    client = httpx2.Client(
        base_url="https://api.test/v1", transport=httpx2.MockTransport(lambda r: httpx2.Response(201))
    )
    with pytest.raises(ValidationError, match=f"between 1 and {MAX_NAME_LENGTH} characters"):
        signup(email="jane@acme.com", first_name="x" * (MAX_NAME_LENGTH + 1), last_name="Doe", http_client=client)


def test_surrounding_whitespace_is_trimmed_before_request() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["body"] = request.read()
        return httpx2.Response(201, json=_RESPONSE)

    client = httpx2.Client(base_url="https://api.test/v1", transport=httpx2.MockTransport(handler))
    signup(email="jane@acme.com", first_name="  Jane  ", last_name="Doe", http_client=client)
    assert b'"first_name": "Jane"' in seen["body"] or b'"first_name":"Jane"' in seen["body"]


def test_decomposed_name_is_normalized_to_nfc_before_request() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["body"] = request.read()
        return httpx2.Response(201, json=_RESPONSE)

    client = httpx2.Client(base_url="https://api.test/v1", transport=httpx2.MockTransport(handler))
    decomposed = "José"
    signup(email="jane@acme.com", first_name=decomposed, last_name="Doe", http_client=client)
    body = seen["body"]
    assert isinstance(body, bytes)
    decoded = body.decode()
    assert '"first_name": "José"' in decoded or '"first_name":"José"' in decoded


def test_name_with_non_composing_mark_is_accepted() -> None:
    client = httpx2.Client(
        base_url="https://api.test/v1",
        transport=httpx2.MockTransport(lambda request: httpx2.Response(201, json=_RESPONSE)),
    )
    name = "अनुज"
    result = signup(email="jane@acme.com", first_name=name, last_name="Doe", http_client=client)
    assert isinstance(result, SignupResult)
