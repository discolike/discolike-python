from __future__ import annotations

import json
from typing import Any

import httpx2


class DiscolikeError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        payload: Any = None,  # noqa: ANN401 -- decoded JSON body, shape is server-defined
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class AuthenticationError(DiscolikeError): ...


class PlanAccessError(DiscolikeError): ...


class InsufficientBalanceError(PlanAccessError):
    """A billed request priced above the account's remaining balance (403 ``INSUFFICIENT_BALANCE``).

    ``requested_records`` and ``max_affordable_records`` count in the request's own size unit
    (records, contacts, companies, domains, rows, queries or personas; the message names it), so a
    retry at ``max_affordable_records`` fits; it is 0 when the request fee does not fit or no record
    fits after the fee. A request with no size to lower (a single-company lookup or a single email find) cannot be retried smaller,
    and its message only asks to top up at ``upgrade_url``.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        payload: Any = None,  # noqa: ANN401 -- decoded JSON body, shape is server-defined
        max_affordable_records: int | None = None,
        remaining_usd: float | None = None,
        requested_records: int | None = None,
        upgrade_url: str | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code, payload=payload)
        self.max_affordable_records = max_affordable_records
        self.remaining_usd = remaining_usd
        self.requested_records = requested_records
        self.upgrade_url = upgrade_url


class ValidationError(DiscolikeError): ...


class NotFoundError(DiscolikeError): ...


class ServerError(DiscolikeError): ...


class APIConnectionError(DiscolikeError): ...


class JobFailedError(DiscolikeError): ...


class JobTimeoutError(DiscolikeError): ...


class RateLimitError(DiscolikeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        payload: Any = None,  # noqa: ANN401 -- decoded JSON body, shape is server-defined
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code, payload=payload)
        self.retry_after = retry_after


INSUFFICIENT_BALANCE_CODE = "INSUFFICIENT_BALANCE"

_STATUS_MAP: dict[int, type[DiscolikeError]] = {
    400: ValidationError,
    401: AuthenticationError,
    402: PlanAccessError,
    403: PlanAccessError,
    404: NotFoundError,
    409: ValidationError,
    422: ValidationError,
}


def _extract_message(response: httpx2.Response) -> tuple[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:500] or f"HTTP {response.status_code}", None
    detail = payload.get("detail") if isinstance(payload, dict) else None
    if isinstance(detail, str):
        return detail, payload
    if isinstance(detail, dict) and isinstance(detail.get("message"), str):
        return detail["message"], payload
    if isinstance(detail, list):
        parts = [
            f"{'.'.join(str(x) for x in item.get('loc', []))}: {item.get('msg', '')}"
            if isinstance(item, dict)
            else str(item)
            for item in detail
        ]
        return "; ".join(parts) or f"HTTP {response.status_code}", payload
    return json.dumps(payload)[:500], payload


def raise_for_status(response: httpx2.Response) -> None:
    if response.status_code < 400:
        return
    message, payload = _extract_message(response)
    if response.status_code == 429:
        header = response.headers.get("Retry-After")
        retry_after = float(header) if header and header.replace(".", "", 1).isdigit() else None
        raise RateLimitError(message, status_code=429, payload=payload, retry_after=retry_after)
    detail = payload.get("detail") if isinstance(payload, dict) else None
    if response.status_code == 403 and isinstance(detail, dict) and detail.get("code") == INSUFFICIENT_BALANCE_CODE:
        raise InsufficientBalanceError(
            message,
            status_code=response.status_code,
            payload=payload,
            max_affordable_records=detail.get("max_affordable_records"),
            remaining_usd=detail.get("remaining_usd"),
            requested_records=detail.get("requested_records"),
            upgrade_url=detail.get("upgrade_url"),
        )
    exc_type = _STATUS_MAP.get(response.status_code, ServerError if response.status_code >= 500 else DiscolikeError)
    raise exc_type(message, status_code=response.status_code, payload=payload)
