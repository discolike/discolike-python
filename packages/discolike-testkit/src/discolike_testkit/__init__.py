"""Shared test fixtures for the discolike workspace.

The fixtures live in :mod:`discolike_testkit.plugin`, which pytest loads
automatically through this package's ``pytest11`` entry point. Tests do not
import the fixtures -- pytest injects them -- but they do import the type
aliases below to annotate the injected parameters, which keeps ``ty`` checking
the calls made through them.
"""

from collections.abc import Callable

import httpx

from discolike import AsyncDiscolike
from discolike import Discolike

__all__ = ["AsyncClientFactory", "ClientFactory", "Handler"]

Handler = Callable[[httpx.Request], httpx.Response]
ClientFactory = Callable[[Handler], Discolike]
AsyncClientFactory = Callable[[Handler], AsyncDiscolike]
