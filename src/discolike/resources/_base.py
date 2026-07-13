from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from discolike._transport import AsyncTransport, Transport

F = TypeVar("F", bound=Callable[..., Any])


def api_route(method: str, path: str, *, openapi: bool = True) -> Callable[[F], F]:
    def stamp(fn: F) -> F:
        fn.__discolike_route__ = (method, path, openapi)  # ty: ignore[unresolved-attribute]
        return fn

    return stamp


def get_discolike_route(fn: object) -> tuple[str, str, bool] | None:
    return getattr(fn, "__discolike_route__", None)


class SyncAPIResource:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport


class AsyncAPIResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport
