from typing import cast

import httpx
import pytest

from discolike import (
    AuthenticationError,
    DiscolikeError,
    NotFoundError,
    PlanAccessError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from discolike._exceptions import raise_for_status


def _response(status: int, json_body: dict | None = None, headers: dict | None = None) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        json=json_body if json_body is not None else {"detail": "boom"},
        headers=headers or {},
        request=httpx.Request("GET", "https://api.test/v1/x"),
    )


@pytest.mark.parametrize(
    ("status", "exc_type"),
    [
        (400, ValidationError),
        (422, ValidationError),
        (401, AuthenticationError),
        (402, PlanAccessError),
        (403, PlanAccessError),
        (404, NotFoundError),
        (429, RateLimitError),
        (500, ServerError),
        (503, ServerError),
    ],
)
def test_status_mapping(status: int, exc_type: type) -> None:
    with pytest.raises(cast(type[DiscolikeError], exc_type)) as exc_info:
        raise_for_status(_response(status))
    assert exc_info.value.status_code == status
    assert "boom" in str(exc_info.value)


def test_ok_passes() -> None:
    raise_for_status(_response(200))


def test_rate_limit_retry_after() -> None:
    with pytest.raises(RateLimitError) as exc_info:
        raise_for_status(_response(429, headers={"Retry-After": "17"}))
    assert exc_info.value.retry_after == 17.0


def test_fastapi_validation_detail_list() -> None:
    body = {"detail": [{"loc": ["query", "domain"], "msg": "field required", "type": "missing"}]}
    with pytest.raises(ValidationError) as exc_info:
        raise_for_status(_response(422, json_body=body))
    assert "domain" in str(exc_info.value)


def test_all_are_discolike_errors() -> None:
    assert issubclass(RateLimitError, DiscolikeError)
