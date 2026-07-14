from __future__ import annotations

import functools
import json
import sys
from collections.abc import Callable
from typing import Any
from typing import ParamSpec
from typing import Protocol
from typing import TypeVar

import typer
from rich.console import Console
from rich.table import Table

from discolike._exceptions import APIConnectionError
from discolike._exceptions import AuthenticationError
from discolike._exceptions import DiscolikeError
from discolike._exceptions import NotFoundError
from discolike._exceptions import PlanAccessError
from discolike._exceptions import RateLimitError
from discolike._exceptions import ValidationError
from discolike._models import DiscolikeModel

P = ParamSpec("P")
R = TypeVar("R")

EXIT_CODES: dict[type, int] = {
    ValidationError: 2,
    AuthenticationError: 3,
    PlanAccessError: 3,
    RateLimitError: 4,
    APIConnectionError: 5,
    NotFoundError: 6,
}
DEFAULT_EXIT_CODE = 1


class _JobStatusLike(Protocol):
    results: Any

    @property
    def progress(self) -> int | None: ...

    def to_dict(self) -> dict[str, Any]: ...


class SupportsWait(Protocol):
    task_id: str
    task_family: str

    def wait(self, *, timeout: float, on_poll: Callable[[_JobStatusLike], None] | None = None) -> _JobStatusLike: ...


def _normalize(data: Any) -> Any:  # noqa: ANN401 -- accepts arbitrary JSON-serializable CLI output data
    if isinstance(data, DiscolikeModel):
        return data.to_dict()
    if isinstance(data, list):
        return [item.to_dict() if isinstance(item, DiscolikeModel) else item for item in data]
    return data


TABLE_CELL_MAX_CHARS = 80
TABLE_MAX_COLUMNS = 8
_SCALAR_TYPES = (str, int, float, bool, type(None))


def _scalar_columns(rows: list[dict[str, Any]]) -> list[str]:
    columns = [column for column in rows[0] if all(isinstance(row.get(column), _SCALAR_TYPES) for row in rows)]
    return columns[:TABLE_MAX_COLUMNS]


def _qualifies_for_table(data: Any) -> bool:  # noqa: ANN401 -- runtime-narrowed via isinstance, not a fixed shape
    return (
        isinstance(data, list)
        and len(data) > 0
        and all(isinstance(item, dict) for item in data)
        and len(_scalar_columns(data)) > 0
    )


def _cell(value: Any) -> str:  # noqa: ANN401 -- scalar JSON value, narrowed by _scalar_columns
    text = "" if value is None else str(value)
    if len(text) > TABLE_CELL_MAX_CHARS:
        return text[: TABLE_CELL_MAX_CHARS - 1] + "…"
    return text


def _render_table(rows: list[dict[str, Any]]) -> None:
    table = Table()
    columns = _scalar_columns(rows)
    for column in columns:
        table.add_column(column, overflow="ellipsis", no_wrap=True)
    for row in rows:
        table.add_row(*(_cell(row.get(column)) for column in columns))
    Console().print(table)


def emit(data: Any, *, fmt: str | None = None) -> None:  # noqa: ANN401 -- accepts arbitrary JSON-serializable CLI output data
    normalized = _normalize(data)
    want_table = fmt == "table" or (fmt is None and sys.stdout.isatty())
    if want_table and _qualifies_for_table(normalized):
        _render_table(normalized)
        return
    print(json.dumps(normalized, indent=2, default=str))


def fail(exc: DiscolikeError) -> typer.Exit:
    payload: dict[str, Any] = {
        "error": type(exc).__name__,
        "message": str(exc),
        "status_code": exc.status_code,
    }
    if isinstance(exc, RateLimitError) and exc.retry_after is not None:
        payload["retry_after"] = exc.retry_after
    print(json.dumps(payload), file=sys.stderr)
    return typer.Exit(code=EXIT_CODES.get(type(exc), DEFAULT_EXIT_CODE))


def call_typed(fn: Callable[..., R], **kwargs: Any) -> R:  # noqa: ANN401 -- forwarded to a typed SDK method signature
    try:
        return fn(**kwargs)
    except TypeError as exc:
        raise typer.BadParameter(str(exc)) from exc


def handle_errors(fn: Callable[P, R]) -> Callable[P, R]:
    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return fn(*args, **kwargs)
        except DiscolikeError as exc:
            raise fail(exc) from exc

    return wrapper


def run_job(job: SupportsWait, *, wait: bool, timeout: float, fmt: str | None = None) -> None:
    if not wait:
        emit(
            {
                "task_id": job.task_id,
                "task_family": job.task_family,
                "hint": f"poll with: discolike discogen status {job.task_id} --family {job.task_family}",
            }
        )
        return

    def _on_poll(status: _JobStatusLike) -> None:
        sys.stderr.write(f"progress: {status.progress}%\n")

    final = job.wait(timeout=timeout, on_poll=_on_poll)
    emit(final.results if final.results is not None else final.to_dict(), fmt=fmt)
