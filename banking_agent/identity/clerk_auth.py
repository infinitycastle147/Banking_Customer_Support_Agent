import os
from datetime import UTC, datetime

import httpx
from clerk_backend_api import Clerk
from clerk_backend_api.security.types import AuthenticateRequestOptions

from banking_agent.models.clerk_identity import ClerkIdentity


class ClerkAuthenticator:
    def __init__(self) -> None:
        self._secret_key = os.getenv("CLERK_SECRET_KEY", "").strip()
        self._parties = [
            origin.strip()
            for origin in os.getenv("CLERK_AUTHORIZED_PARTIES", "").split(",")
            if origin.strip()
        ]
        self._clerk = Clerk(bearer_auth=self._secret_key) if self._secret_key else None

    def authenticate(self, authorization: str | None) -> ClerkIdentity | None:
        if (
            self._clerk is None
            or not self._parties
            or not authorization
            or not authorization.startswith("Bearer ")
        ):
            return None
        request = httpx.Request(
            "GET", self._parties[0], headers={"Authorization": authorization}
        )
        state = self._clerk.authenticate_request(
            request,
            AuthenticateRequestOptions(
                authorized_parties=self._parties, accepts_token=["session_token"]
            ),
        )
        if not state.is_signed_in or not state.payload:
            return None
        payload = state.payload
        if not payload.get("sub") or not payload.get("sid") or not payload.get("exp"):
            return None
        expires_at = datetime.fromtimestamp(payload["exp"], UTC)
        if expires_at <= datetime.now(UTC):
            return None
        return ClerkIdentity(payload["sub"], payload["sid"], expires_at)
