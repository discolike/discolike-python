from __future__ import annotations

import pathlib
from collections.abc import Callable
from typing import Any
from typing import BinaryIO
from typing import TypeVar

from discolike._transport import AsyncTransport
from discolike._transport import Transport

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


def open_upload(file: pathlib.Path | str | BinaryIO) -> tuple[str, BinaryIO, bool]:
    if isinstance(file, (str, pathlib.Path)):
        path = pathlib.Path(file)
        return path.name, open(path, "rb"), True
    return pathlib.Path(getattr(file, "name", "upload.csv")).name, file, False
