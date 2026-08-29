"""Shared test fixtures for the discolike workspace.

The fixtures live in :mod:`discolike_testkit.plugin`, which pytest loads
automatically through this package's ``pytest11`` entry point. Tests do not
import the fixtures -- pytest injects them -- but they do import the type
aliases below to annotate the injected parameters, which keeps ``ty`` checking
the calls made through them.
"""

from collections.abc import Callable

import httpx2

from discolike import AsyncDiscolike
from discolike import Discolike
from discolike._auth import DiscolikeAuth
from discolike._credentials import ApiKeyCredential

__all__ = ["AsyncClientFactory", "ClientFactory", "Handler", "api_key_auth"]

Handler = Callable[[httpx2.Request], httpx2.Response]
ClientFactory = Callable[[Handler], Discolike]
AsyncClientFactory = Callable[[Handler], AsyncDiscolike]


def api_key_auth(api_key: str) -> DiscolikeAuth:
    """Auth for tests that build a ``Transport`` directly instead of going through ``Discolike``."""
    return DiscolikeAuth(ApiKeyCredential(api_key=api_key))
