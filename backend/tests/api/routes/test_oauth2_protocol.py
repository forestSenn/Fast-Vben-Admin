from base64 import urlsafe_b64encode
from datetime import timedelta
from hashlib import sha256
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import (
    OAuth2AccessToken,
    OAuth2AuthorizationCode,
    OAuth2Client,
    User,
    get_datetime_utc,
)


def test_authorization_code_pkce_refresh_and_revoke_flow(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    client_id = "protocol-test-client"
    redirect_uri = "https://client.example.test/callback"
    verifier = "a" * 43
    challenge = (
        urlsafe_b64encode(sha256(verifier.encode()).digest()).decode().rstrip("=")
    )
    oauth_client = OAuth2Client(
        client_id=client_id,
        name="Protocol test client",
        redirect_uris=redirect_uri,
        authorized_grant_types="authorization_code,refresh_token",
        scopes="read,write",
    )
    db.add(oauth_client)
    db.commit()

    try:
        secret_update_without_reauth = client.patch(
            f"{settings.API_V1_STR}/oauth2/clients/{oauth_client.id}",
            headers=superuser_token_headers,
            json={"client_secret": "new-secret"},
        )
        assert secret_update_without_reauth.status_code == 400
        assert secret_update_without_reauth.json()["code"] == "AUTH_REAUTH_REQUIRED"

        secret_update = client.patch(
            f"{settings.API_V1_STR}/oauth2/clients/{oauth_client.id}",
            headers=superuser_token_headers,
            json={
                "client_secret": "new-secret",
                "current_password": settings.FIRST_SUPERUSER_PASSWORD,
            },
        )
        assert secret_update.status_code == 200

        invalid_redirect = client.get(
            f"{settings.API_V1_STR}/oauth2/authorize",
            headers=superuser_token_headers,
            params={
                "client_id": client_id,
                "redirect_uri": "https://attacker.example.test/callback",
                "code_challenge": challenge,
            },
        )
        assert invalid_redirect.status_code == 400

        missing_pkce = client.get(
            f"{settings.API_V1_STR}/oauth2/authorize",
            headers=superuser_token_headers,
            params={"client_id": client_id, "redirect_uri": redirect_uri},
        )
        assert missing_pkce.status_code == 400

        approval = client.get(
            f"{settings.API_V1_STR}/oauth2/authorize",
            headers=superuser_token_headers,
            params={
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "code_challenge": challenge,
                "scope": "read",
            },
        )
        assert approval.status_code == 200
        assert approval.json()["status"] == "approval_required"

        authorized = client.get(
            f"{settings.API_V1_STR}/oauth2/authorize",
            headers=superuser_token_headers,
            follow_redirects=False,
            params={
                "approved": True,
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "code_challenge": challenge,
                "scope": "read",
                "state": "test-state",
            },
        )
        assert authorized.status_code == 302
        query = parse_qs(urlparse(authorized.headers["location"]).query)
        authorization_code = query["code"][0]
        assert query["state"] == ["test-state"]

        token_response = client.post(
            f"{settings.API_V1_STR}/oauth2/token",
            data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "client_secret": "new-secret",
                "code": authorization_code,
                "redirect_uri": redirect_uri,
                "code_verifier": verifier,
            },
        )
        assert token_response.status_code == 200
        tokens = token_response.json()
        assert tokens["access_token"]
        assert tokens["refresh_token"]

        repeated_code = client.post(
            f"{settings.API_V1_STR}/oauth2/token",
            data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "client_secret": "new-secret",
                "code": authorization_code,
                "redirect_uri": redirect_uri,
                "code_verifier": verifier,
            },
        )
        assert repeated_code.status_code == 400

        refreshed = client.post(
            f"{settings.API_V1_STR}/oauth2/token",
            data={
                "grant_type": "refresh_token",
                "client_id": client_id,
                "client_secret": "new-secret",
                "refresh_token": tokens["refresh_token"],
            },
        )
        assert refreshed.status_code == 200
        refreshed_tokens = refreshed.json()
        assert refreshed_tokens["refresh_token"] != tokens["refresh_token"]

        revoked = client.post(
            f"{settings.API_V1_STR}/oauth2/revoke",
            data={
                "client_id": client_id,
                "client_secret": "new-secret",
                "token": refreshed_tokens["refresh_token"],
            },
        )
        assert revoked.status_code == 204

        rejected_refresh = client.post(
            f"{settings.API_V1_STR}/oauth2/token",
            data={
                "grant_type": "refresh_token",
                "client_id": client_id,
                "client_secret": "new-secret",
                "refresh_token": refreshed_tokens["refresh_token"],
            },
        )
        assert rejected_refresh.status_code == 400
    finally:
        for authorization_code in db.exec(
            select(OAuth2AuthorizationCode).where(
                OAuth2AuthorizationCode.client_id == client_id
            )
        ).all():
            db.delete(authorization_code)
        for token in db.exec(
            select(OAuth2AccessToken).where(OAuth2AccessToken.client_id == client_id)
        ).all():
            db.delete(token)
        db.delete(oauth_client)
        db.commit()


def test_expired_authorization_code_is_rejected(
    client: TestClient, db: Session
) -> None:
    client_id = "expired-code-test-client"
    redirect_uri = "https://client.example.test/callback"
    authorization_code_value = "expired-authorization-code"
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).one()
    oauth_client = OAuth2Client(
        client_id=client_id,
        name="Expired code test client",
        redirect_uris=redirect_uri,
        authorized_grant_types="authorization_code",
    )
    authorization_code = OAuth2AuthorizationCode(
        code_hash=sha256(authorization_code_value.encode()).hexdigest(),
        client_id=client_id,
        user_id=user.id,
        redirect_uri=redirect_uri,
        code_challenge="a" * 43,
        expires_at=get_datetime_utc() - timedelta(seconds=1),
    )
    db.add(oauth_client)
    db.add(authorization_code)
    db.commit()

    try:
        response = client.post(
            f"{settings.API_V1_STR}/oauth2/token",
            data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "code": authorization_code_value,
                "redirect_uri": redirect_uri,
                "code_verifier": "a" * 43,
            },
        )
        assert response.status_code == 400
        assert response.json()["message"] == "OAuth2 authorization code is invalid"
    finally:
        db.delete(authorization_code)
        db.delete(oauth_client)
        db.commit()
