"""CLI-specific fixtures.

Only fixtures live here -- pytest discovers them without an import, so this
file is never imported by name. The workspace-wide client factories come from
the ``discolike-testkit`` plugin.
"""

from collections.abc import Callable
from typing import Any

import httpx2
import pytest

import discolike_cli.main as cli_main
from discolike import Discolike

Handler = Callable[[httpx2.Request], httpx2.Response]


@pytest.fixture
def build_client_calls() -> list[dict[str, Any]]:
    """Records the keyword arguments the CLI passes to its client factory."""
    return []


@pytest.fixture
def install_build_client(
    monkeypatch: pytest.MonkeyPatch,
    make_client: Callable[[Handler], Discolike],
    build_client_calls: list[dict[str, Any]],
) -> Callable[[Handler], None]:
    """Point the CLI's client factory at a mock transport driven by ``handler``."""

    def _install(handler: Handler) -> None:
        def _factory(**kwargs: Any) -> Discolike:
            build_client_calls.append(kwargs)
            return make_client(handler)

        monkeypatch.setattr(cli_main, "build_client", _factory)

    return _install
