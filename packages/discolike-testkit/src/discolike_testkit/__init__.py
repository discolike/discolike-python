"""Shared test fixtures for the discolike workspace.

The fixtures live in :mod:`discolike_testkit.plugin`, which pytest loads
automatically through this package's ``pytest11`` entry point. Tests do not
import the fixtures -- pytest injects them -- but they do import the type
aliases below to annotate the injected parameters, which keeps ``ty`` checking
the calls made through them.
"""

import re
from collections.abc import Callable

import httpx2

from discolike import AsyncDiscolike
from discolike import Discolike
from discolike._auth import DiscolikeAuth
from discolike._credentials import ApiKeyCredential

__all__ = ["AsyncClientFactory", "ClientFactory", "Handler", "api_key_auth", "plain_output"]

Handler = Callable[[httpx2.Request], httpx2.Response]
ClientFactory = Callable[[Handler], Discolike]
AsyncClientFactory = Callable[[Handler], AsyncDiscolike]


def api_key_auth(api_key: str) -> DiscolikeAuth:
    """Auth for tests that build a ``Transport`` directly instead of going through ``Discolike``."""
    return DiscolikeAuth(ApiKeyCredential(api_key=api_key))


_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def plain_output(output: str) -> str:
    """Flatten CLI output for substring assertions.

    typer renders usage errors in a rich panel; on GitHub Actions rich forces color and wraps at
    80 columns, so a message that is one line locally arrives colored and split across box rows.
    """
    return " ".join(_ANSI.sub("", output).replace("│", " ").split())
