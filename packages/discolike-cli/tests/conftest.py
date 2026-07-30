"""CLI-specific fixtures.

Only fixtures live here -- pytest discovers them without an import, so this
file is never imported by name. The workspace-wide client factories come from
the ``discolike-testkit`` plugin.
"""

from collections.abc import Callable

import httpx
import pytest

import discolike_cli.main as cli_main
from discolike import Discolike

Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture
def install_build_client(
    monkeypatch: pytest.MonkeyPatch,
    make_client: Callable[[Handler], Discolike],
) -> Callable[[Handler], None]:
    """Point the CLI's client factory at a mock transport driven by ``handler``."""

    def _install(handler: Handler) -> None:
        monkeypatch.setattr(cli_main, "build_client", lambda **kwargs: make_client(handler))

    return _install
