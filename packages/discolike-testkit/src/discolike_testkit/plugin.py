"""Pytest plugin, auto-registered via the ``pytest11`` entry point.

Everything here is exposed as a fixture, so tests receive the helpers by
injection rather than importing them. That removes the older ``from conftest
import make_client`` pattern, which only resolved because pytest's prepend
import mode puts the test directory on ``sys.path`` -- a run spanning both
suites bound whichever directory landed there first, and the two
``conftest.py`` files stayed interchangeable only by being byte-identical.

Tests still import the type aliases from :mod:`discolike_testkit` to annotate
the injected parameters. That is a plain absolute import of a uniquely named
installed distribution, so it carries none of the ambiguity above.

Registering as a plugin rather than a root ``conftest.py`` also keeps
``no_ambient_credentials`` in force no matter where pytest is invoked from: a
root ``conftest.py`` is skipped entirely when rootdir resolves to a single
package, which would silently let real credentials into a test run.
"""

from pathlib import Path

import httpx2
import pytest

from discolike import AsyncDiscolike
from discolike import Discolike
from discolike_testkit import AsyncClientFactory
from discolike_testkit import ClientFactory
from discolike_testkit import Handler

BASE_URL = "https://api.test/v1"


@pytest.fixture(autouse=True)
def no_ambient_credentials(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("DISCOLIKE_API_KEY", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))


@pytest.fixture
def make_client() -> ClientFactory:
    """Build a sync client whose transport is backed by ``handler``."""

    def _make(handler: Handler) -> Discolike:
        http = httpx2.Client(transport=httpx2.MockTransport(handler), base_url=BASE_URL)
        return Discolike(api_key="test-key", base_url=BASE_URL, http_client=http)

    return _make


@pytest.fixture
def make_async_client() -> AsyncClientFactory:
    """Build an async client whose transport is backed by ``handler``."""

    def _make(handler: Handler) -> AsyncDiscolike:
        http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler), base_url=BASE_URL)
        return AsyncDiscolike(api_key="test-key", base_url=BASE_URL, http_client=http)

    return _make
