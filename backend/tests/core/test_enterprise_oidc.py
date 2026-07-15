from base64 import urlsafe_b64encode
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from app.core.config import settings
from app.core.enterprise_oidc import validate_identity_token


def encode_jwk_number(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return urlsafe_b64encode(raw).decode().rstrip("=")


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def json(self) -> dict[str, object]:
        return self.payload

    def raise_for_status(self) -> None:
        return None


def test_identity_token_requires_matching_signature_audience_issuer_and_nonce(
    monkeypatch,
) -> None:
    issuer = "https://idp.example.test"
    client_id = "enterprise-client"
    nonce = "test-nonce"
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_numbers = private_key.public_key().public_numbers()
    token = jwt.encode(
        {
            "aud": client_id,
            "email": "user@example.com",
            "email_verified": True,
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "iat": datetime.now(UTC),
            "iss": issuer,
            "nonce": nonce,
            "sub": "enterprise-subject",
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )
    monkeypatch.setattr(settings, "ENTERPRISE_OIDC_CLIENT_ID", client_id)
    monkeypatch.setattr(
        "app.core.enterprise_oidc.httpx.get",
        lambda url, timeout: FakeResponse(
            {
                "keys": [
                    {
                        "alg": "RS256",
                        "e": encode_jwk_number(public_numbers.e),
                        "kid": "test-key",
                        "kty": "RSA",
                        "n": encode_jwk_number(public_numbers.n),
                        "use": "sig",
                    }
                ]
            }
        ),
    )
    metadata = {"issuer": issuer, "jwks_uri": f"{issuer}/jwks"}

    claims = validate_identity_token(
        id_token=token,
        metadata=metadata,
        expected_nonce=nonce,
    )
    assert claims["sub"] == "enterprise-subject"

    with pytest.raises(HTTPException, match="identity token is invalid"):
        validate_identity_token(
            id_token=token,
            metadata=metadata,
            expected_nonce="different-nonce",
        )
