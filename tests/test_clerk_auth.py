from datetime import UTC, datetime, timedelta

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from banking_agent.identity.clerk_auth import ClerkAuthenticator


def test_clerk_token_requires_valid_signature_origin_and_expiry(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    monkeypatch.setattr(
        "clerk_backend_api.security.verifytoken._get_remote_jwt_key",
        lambda _token, _options: public_key.decode(),
    )
    monkeypatch.setenv("CLERK_SECRET_KEY", "test-secret")
    monkeypatch.setenv("CLERK_AUTHORIZED_PARTIES", "http://127.0.0.1:5173")
    authenticator = ClerkAuthenticator()
    now = datetime.now(UTC)
    claims = {
        "sub": "user-a",
        "sid": "session-a",
        "azp": "http://127.0.0.1:5173",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=2)).timestamp()),
    }

    def signed(payload):
        return "Bearer " + jwt.encode(
            payload, private_key, algorithm="RS256", headers={"kid": "test-key"}
        )

    assert authenticator.authenticate(signed(claims)).user_id == "user-a"
    assert (
        authenticator.authenticate(signed({**claims, "azp": "https://other.test"}))
        is None
    )
    assert (
        authenticator.authenticate(
            signed({**claims, "exp": int((now - timedelta(minutes=1)).timestamp())})
        )
        is None
    )
    assert authenticator.authenticate("Bearer invalid") is None
    assert authenticator.authenticate("invalid") is None
