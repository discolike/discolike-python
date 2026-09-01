"""Credential-free account creation, for agents opening an account on a person's behalf."""

from __future__ import annotations

import httpx2

from discolike._client import DEFAULT_TIMEOUT_SECONDS
from discolike._config import DEFAULT_BASE_URL
from discolike._exceptions import APIConnectionError
from discolike._exceptions import raise_for_status
from discolike._models import DiscolikeModel
from discolike._version import __version__

SIGNUP_PATH = "/public/signup"
DEFAULT_AGENT = f"discolike-python/{__version__}"


class SignupResult(DiscolikeModel):
    status: str
    email: str
    org_domain: str
    org_status: str
    next_step: str


def _body(*, email: str, first_name: str, last_name: str, agent: str | None) -> dict[str, str]:
    return {"email": email, "first_name": first_name, "last_name": last_name, "agent": agent or DEFAULT_AGENT}


def signup(
    *,
    email: str,
    first_name: str,
    last_name: str,
    agent: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    http_client: httpx2.Client | None = None,
) -> SignupResult:
    """Create a DiscoLike account for ``email``. No credential is returned; the person
    confirms by email and logs in at https://app.discolike.com."""
    client = http_client or httpx2.Client(base_url=base_url, timeout=timeout)
    try:
        response = client.post(
            SIGNUP_PATH,
            json=_body(email=email, first_name=first_name, last_name=last_name, agent=agent),
            headers={"User-Agent": DEFAULT_AGENT},
        )
    except httpx2.TransportError as exc:
        raise APIConnectionError(f"Connection to DiscoLike API failed: {exc}") from exc
    finally:
        if http_client is None:
            client.close()
    raise_for_status(response)
    return SignupResult.model_validate(response.json())


async def async_signup(
    *,
    email: str,
    first_name: str,
    last_name: str,
    agent: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    http_client: httpx2.AsyncClient | None = None,
) -> SignupResult:
    client = http_client or httpx2.AsyncClient(base_url=base_url, timeout=timeout)
    try:
        response = await client.post(
            SIGNUP_PATH,
            json=_body(email=email, first_name=first_name, last_name=last_name, agent=agent),
            headers={"User-Agent": DEFAULT_AGENT},
        )
    except httpx2.TransportError as exc:
        raise APIConnectionError(f"Connection to DiscoLike API failed: {exc}") from exc
    finally:
        if http_client is None:
            await client.aclose()
    raise_for_status(response)
    return SignupResult.model_validate(response.json())
