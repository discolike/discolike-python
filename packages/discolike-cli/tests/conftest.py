import httpx
import pytest

from discolike import AsyncDiscolike
from discolike import Discolike

BASE_URL = "https://api.test/v1"


def make_client(handler) -> Discolike:
    http = httpx.Client(transport=httpx.MockTransport(handler), base_url=BASE_URL)
    return Discolike(api_key="test-key", base_url=BASE_URL, http_client=http)


def make_async_client(handler) -> AsyncDiscolike:
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url=BASE_URL)
    return AsyncDiscolike(api_key="test-key", base_url=BASE_URL, http_client=http)


@pytest.fixture(autouse=True)
def no_ambient_credentials(monkeypatch, tmp_path):
    monkeypatch.delenv("DISCOLIKE_API_KEY", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
