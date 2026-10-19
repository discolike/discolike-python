from typing import cast

import httpx2
import pytest

from discolike import AuthenticationError
from discolike import DiscolikeError
from discolike import InsufficientBalanceError
from discolike import NotFoundError
from discolike import PlanAccessError
from discolike import RateLimitError
from discolike import ServerError
from discolike import ValidationError
from discolike._exceptions import raise_for_status


def _response(status: int, json_body: dict | None = None, headers: dict | None = None) -> httpx2.Response:
    return httpx2.Response(
        status_code=status,
        json=json_body if json_body is not None else {"detail": "boom"},
        headers=headers or {},
        request=httpx2.Request("GET", "https://api.test/v1/x"),
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
        (409, ValidationError),
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


def test_detail_list_with_non_dict_items() -> None:
    with pytest.raises(ValidationError) as exc_info:
        raise_for_status(_response(422, json_body={"detail": ["some string error"]}))
    assert "some string error" in str(exc_info.value)


def test_all_are_discolike_errors() -> None:
    assert issubclass(RateLimitError, DiscolikeError)


INSUFFICIENT_BALANCE_DETAIL = {
    "code": "INSUFFICIENT_BALANCE",
    "message": (
        "This request could cost up to $140.70 but the account has $43.75 left this cycle. "
        "Lower it to at most 3075 records, or upgrade or top up to continue."
    ),
    "remaining_usd": 43.75,
    "max_affordable_records": 3075,
    "requested_records": 10000,
    "upgrade_url": "https://app.discolike.com/account/management/plans",
}


def test_insufficient_balance_403_raises_typed_error_with_fields() -> None:
    with pytest.raises(InsufficientBalanceError) as exc_info:
        raise_for_status(_response(403, json_body={"detail": INSUFFICIENT_BALANCE_DETAIL}))
    err = exc_info.value
    assert isinstance(err, PlanAccessError)
    assert str(err) == INSUFFICIENT_BALANCE_DETAIL["message"]
    assert err.status_code == 403
    assert err.max_affordable_records == 3075
    assert err.remaining_usd == 43.75
    assert err.requested_records == 10000
    assert err.upgrade_url == "https://app.discolike.com/account/management/plans"
    assert err.payload == {"detail": INSUFFICIENT_BALANCE_DETAIL}


def test_insufficient_balance_code_on_another_status_is_not_a_balance_error() -> None:
    with pytest.raises(ServerError) as exc_info:
        raise_for_status(_response(500, json_body={"detail": INSUFFICIENT_BALANCE_DETAIL}))
    assert not isinstance(exc_info.value, InsufficientBalanceError)


def test_other_dict_detail_uses_its_message() -> None:
    body = {"detail": {"code": "SOMETHING_ELSE", "message": "not allowed"}}
    with pytest.raises(PlanAccessError) as exc_info:
        raise_for_status(_response(403, json_body=body))
    assert type(exc_info.value) is PlanAccessError
    assert str(exc_info.value) == "not allowed"


def test_plain_403_stays_plan_access_error() -> None:
    with pytest.raises(PlanAccessError) as exc_info:
        raise_for_status(_response(403))
    assert type(exc_info.value) is PlanAccessError


def test_no_credentials_401_object_detail_uses_its_message() -> None:
    body = {
        "detail": {
            "code": "UNAUTHENTICATED",
            "message": "No credentials. A human can create a free account (no card).",
            "signup_url": "https://api.discolike.com/v1/public/signup",
            "plan": "free",
            "allowance_usd": 5.0,
            "cpc": 0.7,
            "cpm": 14.0,
        }
    }
    with pytest.raises(AuthenticationError) as exc_info:
        raise_for_status(_response(401, json_body=body))
    assert str(exc_info.value) == "No credentials. A human can create a free account (no card)."
    assert exc_info.value.payload["detail"]["signup_url"] == "https://api.discolike.com/v1/public/signup"
