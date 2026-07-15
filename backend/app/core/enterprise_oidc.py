import json
from base64 import urlsafe_b64encode
from hashlib import sha256
from secrets import token_urlsafe
from typing import Any

import httpx
import jwt
from fastapi import HTTPException

from app.core.config import settings

OIDC_PROVIDER = "enterprise_oidc"
OIDC_SIGNING_ALGORITHMS = {"ES256", "ES384", "ES512", "RS256", "RS384", "RS512"}


def hash_oidc_value(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def generate_oidc_value() -> str:
    return token_urlsafe(48)


def build_pkce_challenge(verifier: str) -> str:
    return urlsafe_b64encode(sha256(verifier.encode()).digest()).decode().rstrip("=")


def ensure_enterprise_oidc_configured() -> None:
    if not settings.ENTERPRISE_OIDC_ENABLED:
        raise HTTPException(status_code=404, detail="Enterprise OIDC is disabled")
    required = (
        settings.ENTERPRISE_OIDC_CLIENT_ID,
        settings.ENTERPRISE_OIDC_CLIENT_SECRET,
        settings.ENTERPRISE_OIDC_REDIRECT_URI,
        settings.ENTERPRISE_OIDC_ISSUER,
    )
    if not all(required):
        raise HTTPException(status_code=503, detail="Enterprise OIDC is not configured")


def discovery_url() -> str:
    if settings.ENTERPRISE_OIDC_DISCOVERY_URL:
        return settings.ENTERPRISE_OIDC_DISCOVERY_URL
    issuer = (settings.ENTERPRISE_OIDC_ISSUER or "").rstrip("/")
    return f"{issuer}/.well-known/openid-configuration"


def require_secure_url(url: str) -> None:
    if settings.ENVIRONMENT != "local" and not url.startswith("https://"):
        raise HTTPException(status_code=503, detail="Enterprise OIDC is not configured")


def get_oidc_provider_metadata() -> dict[str, Any]:
    ensure_enterprise_oidc_configured()
    metadata_url = discovery_url()
    require_secure_url(metadata_url)
    try:
        response = httpx.get(
            metadata_url, timeout=settings.ENTERPRISE_OIDC_HTTP_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        metadata = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=503, detail="Enterprise OIDC is not configured"
        ) from exc

    required_keys = ("authorization_endpoint", "issuer", "jwks_uri", "token_endpoint")
    if not isinstance(metadata, dict) or any(
        not metadata.get(key) for key in required_keys
    ):
        raise HTTPException(status_code=503, detail="Enterprise OIDC is not configured")
    configured_issuer = (settings.ENTERPRISE_OIDC_ISSUER or "").rstrip("/")
    if str(metadata["issuer"]).rstrip("/") != configured_issuer:
        raise HTTPException(status_code=503, detail="Enterprise OIDC is not configured")
    for key in ("authorization_endpoint", "jwks_uri", "token_endpoint"):
        require_secure_url(str(metadata[key]))
    return metadata


def exchange_authorization_code(
    *, metadata: dict[str, Any], code: str, code_verifier: str
) -> str:
    try:
        response = httpx.post(
            str(metadata["token_endpoint"]),
            auth=(
                settings.ENTERPRISE_OIDC_CLIENT_ID or "",
                settings.ENTERPRISE_OIDC_CLIENT_SECRET or "",
            ),
            data={
                "code": code,
                "code_verifier": code_verifier,
                "grant_type": "authorization_code",
                "redirect_uri": settings.ENTERPRISE_OIDC_REDIRECT_URI or "",
            },
            timeout=settings.ENTERPRISE_OIDC_HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=401, detail="Enterprise OIDC identity token is invalid"
        ) from exc
    id_token = payload.get("id_token") if isinstance(payload, dict) else None
    if not isinstance(id_token, str) or not id_token:
        raise HTTPException(
            status_code=401, detail="Enterprise OIDC identity token is invalid"
        )
    return id_token


def validate_identity_token(
    *, id_token: str, metadata: dict[str, Any], expected_nonce: str
) -> dict[str, Any]:
    try:
        header = jwt.get_unverified_header(id_token)
        algorithm = header.get("alg")
        key_id = header.get("kid")
        if algorithm not in OIDC_SIGNING_ALGORITHMS or not key_id:
            raise ValueError("Unsupported signing algorithm")
        response = httpx.get(
            str(metadata["jwks_uri"]),
            timeout=settings.ENTERPRISE_OIDC_HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        jwks = response.json()
        keys = jwks.get("keys", []) if isinstance(jwks, dict) else []
        jwk = next((key for key in keys if key.get("kid") == key_id), None)
        if not isinstance(jwk, dict):
            raise ValueError("Signing key is not available")
        signing_key = jwt.PyJWK.from_dict(jwk).key
        claims = jwt.decode(
            id_token,
            signing_key,
            algorithms=[algorithm],
            audience=settings.ENTERPRISE_OIDC_CLIENT_ID,
            issuer=metadata["issuer"],
            options={"require": ["exp", "iat", "iss", "sub"]},
        )
    except (jwt.PyJWTError, httpx.HTTPError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=401, detail="Enterprise OIDC identity token is invalid"
        ) from exc
    if claims.get("nonce") != expected_nonce:
        raise HTTPException(
            status_code=401, detail="Enterprise OIDC identity token is invalid"
        )
    return claims


def role_codes_from_claims(claims: dict[str, Any]) -> set[str]:
    if settings.ENTERPRISE_OIDC_ROLE_SYNC_MODE == "disabled":
        return set()
    try:
        mapping = json.loads(settings.ENTERPRISE_OIDC_ROLE_MAPPING)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=503, detail="Enterprise OIDC is not configured"
        ) from exc
    if not isinstance(mapping, dict):
        raise HTTPException(status_code=503, detail="Enterprise OIDC is not configured")
    raw_groups = claims.get(settings.ENTERPRISE_OIDC_ROLE_CLAIM, [])
    if isinstance(raw_groups, str):
        groups = {raw_groups}
    elif isinstance(raw_groups, list) and all(
        isinstance(group, str) for group in raw_groups
    ):
        groups = set(raw_groups)
    else:
        raise HTTPException(
            status_code=401, detail="Enterprise OIDC identity token is invalid"
        )
    role_codes: set[str] = set()
    for group in groups:
        mapped = mapping.get(str(group))
        if isinstance(mapped, str):
            role_codes.add(mapped)
        elif isinstance(mapped, list) and all(isinstance(code, str) for code in mapped):
            role_codes.update(mapped)
    return role_codes


def external_identity_is_active(claims: dict[str, Any]) -> bool:
    value = claims.get(settings.ENTERPRISE_OIDC_ACTIVE_CLAIM)
    return value is not False
