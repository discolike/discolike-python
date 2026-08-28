from __future__ import annotations

import time
from dataclasses import asdict
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ApiKeyCredential:
    api_key: str


@dataclass(frozen=True)
class OAuthCredential:
    access_token: str
    refresh_token: str
    expires_at: float
    client_id: str
    token_endpoint: str

    def expires_within(self, seconds: float, *, now: float | None = None) -> bool:
        current = time.time() if now is None else now
        return self.expires_at - current <= seconds

    @classmethod
    def from_config(cls, data: dict[str, Any]) -> OAuthCredential:
        return cls(
            access_token=str(data["access_token"]),
            refresh_token=str(data["refresh_token"]),
            expires_at=float(data["expires_at"]),
            client_id=str(data["client_id"]),
            token_endpoint=str(data["token_endpoint"]),
        )

    def to_config(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OAuthClientRegistration:
    client_id: str
    redirect_uri: str
    issuer: str

    @classmethod
    def from_config(cls, data: dict[str, Any]) -> OAuthClientRegistration:
        return cls(client_id=str(data["client_id"]), redirect_uri=str(data["redirect_uri"]), issuer=str(data["issuer"]))

    def to_config(self) -> dict[str, Any]:
        return asdict(self)


Credential = ApiKeyCredential | OAuthCredential
