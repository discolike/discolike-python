import stat

import pytest

from discolike import AuthenticationError
from discolike._config import config_path
from discolike._config import delete_credential
from discolike._config import delete_oauth_client
from discolike._config import load_config
from discolike._config import load_credential
from discolike._config import load_oauth_client
from discolike._config import resolve_credential
from discolike._config import save_config
from discolike._config import save_credential
from discolike._config import save_oauth_client
from discolike._credentials import ApiKeyCredential
from discolike._credentials import OAuthClientRegistration
from discolike._credentials import OAuthCredential


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("DISCOLIKE_API_KEY", raising=False)
    return tmp_path


def test_save_and_load_roundtrip(isolated_config) -> None:
    save_config({"auth_method": "api_key", "api_key": "dk-123"})
    assert load_config()["api_key"] == "dk-123"
    mode = stat.S_IMODE(config_path().stat().st_mode)
    assert mode == 0o600


def test_save_tightens_preexisting_loose_mode(isolated_config) -> None:
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text("{}")
    config_path().chmod(0o644)
    save_config({"auth_method": "api_key", "api_key": "dk-456"})
    assert load_config()["api_key"] == "dk-456"
    mode = stat.S_IMODE(config_path().stat().st_mode)
    assert mode == 0o600


def test_load_missing_returns_empty(isolated_config) -> None:
    assert load_config() == {}


def test_corrupt_config_returns_empty(isolated_config) -> None:
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text("{not json")
    assert load_config() == {}


def test_binary_garbage_config_returns_empty(isolated_config) -> None:
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_bytes(b"\xff\xfe\x00garbage")
    assert load_config() == {}


def _oauth_credential() -> OAuthCredential:
    return OAuthCredential(
        access_token="at",
        refresh_token="rt",
        expires_at=1.0,
        client_id="c",
        token_endpoint="https://t/token",
        resource="https://api.example.com/v1",
    )


def test_save_and_load_oauth_credential(isolated_config) -> None:
    save_credential(_oauth_credential())
    stored = load_config()
    assert stored["auth_method"] == "oauth"
    assert stored["oauth"] == {
        "access_token": "at",
        "refresh_token": "rt",
        "expires_at": 1.0,
        "client_id": "c",
        "token_endpoint": "https://t/token",
        "resource": "https://api.example.com/v1",
    }
    assert load_credential() == _oauth_credential()


def test_load_oauth_credential_saved_before_resource_was_stored(isolated_config) -> None:
    """Config written by 0.3.x has no `resource`; it must still load, and refresh then omits the field."""
    save_config(
        {
            "auth_method": "oauth",
            "oauth": {
                "access_token": "at",
                "refresh_token": "rt",
                "expires_at": 1.0,
                "client_id": "c",
                "token_endpoint": "https://t/token",
            },
        }
    )
    loaded = load_credential()
    assert isinstance(loaded, OAuthCredential)
    assert loaded.resource is None


def test_save_api_key_credential_keeps_legacy_shape(isolated_config) -> None:
    save_credential(ApiKeyCredential(api_key="dk-1"))
    assert load_config() == {"auth_method": "api_key", "api_key": "dk-1"}


def test_load_credential_without_auth_method_is_api_key(isolated_config) -> None:
    save_config({"api_key": "legacy"})
    assert load_credential() == ApiKeyCredential(api_key="legacy")
    assert resolve_credential() == ApiKeyCredential(api_key="legacy")


def test_load_credential_missing_returns_none(isolated_config) -> None:
    assert load_credential() is None


def test_resolve_credential_precedence(isolated_config, monkeypatch) -> None:
    save_credential(_oauth_credential())
    monkeypatch.setenv("DISCOLIKE_API_KEY", "from-env")
    injected = ApiKeyCredential(api_key="injected")
    assert resolve_credential(api_key="explicit", auth=injected) is injected
    assert resolve_credential(api_key="explicit") == ApiKeyCredential(api_key="explicit")
    assert resolve_credential() == ApiKeyCredential(api_key="from-env")
    monkeypatch.delenv("DISCOLIKE_API_KEY")
    assert resolve_credential() == _oauth_credential()


def test_resolve_credential_nothing_raises_with_guidance(isolated_config) -> None:
    with pytest.raises(AuthenticationError, match="discolike auth login"):
        resolve_credential()


def test_save_config_is_atomic_and_leaves_no_temp_files(isolated_config) -> None:
    save_config({"auth_method": "api_key", "api_key": "first"})
    save_config({"auth_method": "api_key", "api_key": "second"})
    assert [entry.name for entry in config_path().parent.iterdir()] == [config_path().name]
    assert load_config()["api_key"] == "second"
    assert stat.S_IMODE(config_path().stat().st_mode) == 0o600


REGISTRATION = OAuthClientRegistration(
    client_id="client-1", redirect_uri="http://127.0.0.1:18484/callback", issuer="https://auth.test/oauth/2.1"
)


def test_oauth_client_registration_roundtrip_and_missing(isolated_config) -> None:
    assert load_oauth_client() is None
    save_oauth_client(REGISTRATION)
    assert load_oauth_client() == REGISTRATION
    assert load_config()["oauth_client"] == REGISTRATION.to_config()


def test_save_credential_preserves_oauth_client(isolated_config) -> None:
    save_oauth_client(REGISTRATION)
    save_credential(_oauth_credential())
    assert load_oauth_client() == REGISTRATION
    assert load_credential() == _oauth_credential()
    save_credential(ApiKeyCredential(api_key="dk-1"))
    assert load_oauth_client() == REGISTRATION
    assert load_credential() == ApiKeyCredential(api_key="dk-1")


def test_save_oauth_client_preserves_credential(isolated_config) -> None:
    save_credential(_oauth_credential())
    save_oauth_client(REGISTRATION)
    assert load_credential() == _oauth_credential()


def test_delete_credential_keeps_oauth_client(isolated_config) -> None:
    save_oauth_client(REGISTRATION)
    save_credential(_oauth_credential())
    delete_credential()
    assert load_credential() is None
    assert load_oauth_client() == REGISTRATION
    assert load_config() == {"oauth_client": REGISTRATION.to_config()}


def test_delete_credential_without_oauth_client_removes_file(isolated_config) -> None:
    save_credential(ApiKeyCredential(api_key="dk-1"))
    delete_credential()
    assert not config_path().exists()
    delete_credential()


@pytest.mark.parametrize(
    "config",
    [
        {"auth_method": "oauth"},
        {"auth_method": "oauth", "oauth": "not-a-dict"},
        {"auth_method": "oauth", "oauth": {"access_token": "a", "refresh_token": "r"}},
        {"auth_method": "oauth", "oauth": {**_oauth_credential().to_config(), "expires_at": "soon"}},
    ],
)
def test_malformed_oauth_section_is_no_credential(isolated_config, config) -> None:
    save_config(config)
    assert load_credential() is None
    with pytest.raises(AuthenticationError, match="discolike auth login"):
        resolve_credential()


@pytest.mark.parametrize("stored", ["not-a-dict", {"client_id": "c"}, 7])
def test_malformed_oauth_client_is_none(isolated_config, stored) -> None:
    save_config({"oauth_client": stored})
    assert load_oauth_client() is None


def test_delete_oauth_client_keeps_credential(isolated_config) -> None:
    save_credential(_oauth_credential())
    save_oauth_client(REGISTRATION)
    delete_oauth_client()
    assert load_oauth_client() is None
    assert load_credential() == _oauth_credential()
    delete_oauth_client()
