import uuid
from base64 import urlsafe_b64encode
from datetime import timedelta
from hashlib import sha256
from secrets import token_urlsafe
from typing import Any
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, Depends, Form, HTTPException, Response
from fastapi.responses import RedirectResponse
from sqlmodel import col, func, or_, select

from app.api.deps import (
    CurrentUser,
    SessionDep,
    normalize_pagination,
    require_permission,
)
from app.core.mfa import decrypt_secret, encrypt_secret
from app.core.security import verify_password
from app.models import (
    OAuth2AccessToken,
    OAuth2AccessTokenPublic,
    OAuth2AccessTokensPublic,
    OAuth2AuthorizationCode,
    OAuth2Client,
    OAuth2ClientCreate,
    OAuth2ClientPublic,
    OAuth2ClientsPublic,
    OAuth2ClientUpdate,
    User,
    get_datetime_utc,
)

router = APIRouter(prefix="/oauth2", tags=["oauth2"])


def hash_oauth2_value(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def split_csv(value: str | None) -> set[str]:
    return {item.strip() for item in (value or "").split(",") if item.strip()}


def validate_redirect_uri(client: OAuth2Client, redirect_uri: str) -> None:
    if redirect_uri not in split_csv(client.redirect_uris):
        raise HTTPException(status_code=400, detail="OAuth2 redirect URI is invalid")


def validate_requested_scopes(client: OAuth2Client, scope: str | None) -> str:
    requested = split_csv(scope.replace(" ", ",") if scope else "")
    allowed = split_csv(client.scopes)
    if not requested:
        return ""
    if not requested <= allowed:
        raise HTTPException(status_code=400, detail="OAuth2 scope is invalid")
    return " ".join(sorted(requested))


def authenticate_protocol_client(
    *, session: SessionDep, client_id: str, client_secret: str | None
) -> OAuth2Client:
    client = session.exec(
        select(OAuth2Client).where(OAuth2Client.client_id == client_id)
    ).first()
    if not client or not client.is_active:
        raise HTTPException(
            status_code=401, detail="OAuth2 client authentication failed"
        )
    if client.client_secret:
        if not client_secret:
            raise HTTPException(
                status_code=401, detail="OAuth2 client authentication failed"
            )
        try:
            expected_secret = decrypt_secret(client.client_secret)
        except ValueError:
            raise HTTPException(
                status_code=401, detail="OAuth2 client authentication failed"
            )
        if expected_secret != client_secret:
            raise HTTPException(
                status_code=401, detail="OAuth2 client authentication failed"
            )
    return client


def revoke_token_family(session: SessionDep, token_family_id: uuid.UUID | None) -> None:
    if not token_family_id:
        return
    tokens = session.exec(
        select(OAuth2AccessToken).where(
            OAuth2AccessToken.token_family_id == token_family_id,
            OAuth2AccessToken.revoked_at.is_(None),
        )
    ).all()
    now = get_datetime_utc()
    for token in tokens:
        token.revoked_at = now
        session.add(token)


@router.get("/authorize", response_model=None)
def authorize_oauth2(
    session: SessionDep,
    current_user: CurrentUser,
    client_id: str,
    redirect_uri: str,
    response_type: str = "code",
    code_challenge: str = "",
    code_challenge_method: str = "S256",
    scope: str | None = None,
    state: str | None = None,
    approved: bool = False,
) -> dict[str, str] | RedirectResponse:
    client = session.exec(
        select(OAuth2Client).where(OAuth2Client.client_id == client_id)
    ).first()
    if not client or not client.is_active:
        raise HTTPException(status_code=400, detail="OAuth2 client is invalid")
    validate_redirect_uri(client, redirect_uri)
    if response_type != "code" or "authorization_code" not in split_csv(
        client.authorized_grant_types
    ):
        raise HTTPException(status_code=400, detail="OAuth2 response type is invalid")
    if code_challenge_method != "S256" or not 43 <= len(code_challenge) <= 128:
        raise HTTPException(status_code=400, detail="OAuth2 PKCE challenge is invalid")
    scopes = validate_requested_scopes(client, scope)
    if not approved:
        return {
            "client_name": client.name,
            "scope": scopes,
            "status": "approval_required",
        }

    authorization_code = token_urlsafe(32)
    session.add(
        OAuth2AuthorizationCode(
            code_hash=hash_oauth2_value(authorization_code),
            client_id=client.client_id,
            user_id=current_user.id,
            redirect_uri=redirect_uri,
            scopes=scopes or None,
            code_challenge=code_challenge,
            expires_at=get_datetime_utc() + timedelta(minutes=5),
        )
    )
    session.commit()
    query = {"code": authorization_code}
    if state:
        query["state"] = state
    separator = "&" if urlparse(redirect_uri).query else "?"
    return RedirectResponse(
        url=f"{redirect_uri}{separator}{urlencode(query)}", status_code=302
    )


@router.post("/token")
def exchange_oauth2_token(
    session: SessionDep,
    grant_type: str = Form(...),
    client_id: str = Form(...),
    client_secret: str | None = Form(default=None),
    code: str | None = Form(default=None),
    redirect_uri: str | None = Form(default=None),
    code_verifier: str | None = Form(default=None),
    refresh_token: str | None = Form(default=None),
) -> dict[str, Any]:
    client = authenticate_protocol_client(
        session=session, client_id=client_id, client_secret=client_secret
    )
    if grant_type == "refresh_token":
        if not refresh_token or "refresh_token" not in split_csv(
            client.authorized_grant_types
        ):
            raise HTTPException(
                status_code=400, detail="OAuth2 token request is invalid"
            )
        token = session.exec(
            select(OAuth2AccessToken).where(
                OAuth2AccessToken.refresh_token_hash
                == hash_oauth2_value(refresh_token),
                OAuth2AccessToken.client_id == client.client_id,
            )
        ).first()
        if (
            not token
            or not token.refresh_expires_at
            or token.refresh_expires_at <= get_datetime_utc()
        ):
            raise HTTPException(
                status_code=400, detail="OAuth2 refresh token is invalid"
            )
        if token.revoked_at is not None:
            revoke_token_family(session, token.token_family_id)
            session.commit()
            raise HTTPException(
                status_code=400, detail="OAuth2 refresh token is invalid"
            )
        access_token = token_urlsafe(32)
        next_refresh_token = token_urlsafe(32)
        now = get_datetime_utc()
        token.revoked_at = now
        session.add(token)
        session.add(
            OAuth2AccessToken(
                access_token_hash=hash_oauth2_value(access_token),
                refresh_token_hash=hash_oauth2_value(next_refresh_token),
                token_family_id=token.token_family_id,
                user_id=token.user_id,
                user_email=token.user_email,
                user_full_name=token.user_full_name,
                client_id=token.client_id,
                scopes=token.scopes,
                expires_at=now
                + timedelta(seconds=client.access_token_validity_seconds),
                refresh_expires_at=now
                + timedelta(seconds=client.refresh_token_validity_seconds),
            )
        )
        session.commit()
        return {
            "access_token": access_token,
            "refresh_token": next_refresh_token,
            "token_type": "Bearer",
            "expires_in": client.access_token_validity_seconds,
            "scope": token.scopes or "",
        }

    if (
        grant_type != "authorization_code"
        or not code
        or not redirect_uri
        or not code_verifier
    ):
        raise HTTPException(status_code=400, detail="OAuth2 token request is invalid")
    authorization_code = session.exec(
        select(OAuth2AuthorizationCode).where(
            OAuth2AuthorizationCode.code_hash == hash_oauth2_value(code)
        )
    ).first()
    if (
        not authorization_code
        or authorization_code.used_at is not None
        or authorization_code.expires_at <= get_datetime_utc()
        or authorization_code.client_id != client.client_id
        or authorization_code.redirect_uri != redirect_uri
    ):
        raise HTTPException(
            status_code=400, detail="OAuth2 authorization code is invalid"
        )
    expected_challenge = (
        urlsafe_b64encode(sha256(code_verifier.encode()).digest()).decode().rstrip("=")
    )
    if expected_challenge != authorization_code.code_challenge:
        raise HTTPException(status_code=400, detail="OAuth2 PKCE verification failed")
    user = session.get(User, authorization_code.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=400, detail="OAuth2 authorization user is invalid"
        )
    access_token = token_urlsafe(32)
    refresh_token = token_urlsafe(32)
    now = get_datetime_utc()
    authorization_code.used_at = now
    session.add(authorization_code)
    session.add(
        OAuth2AccessToken(
            access_token_hash=hash_oauth2_value(access_token),
            refresh_token_hash=hash_oauth2_value(refresh_token),
            token_family_id=uuid.uuid4(),
            user_id=user.id,
            user_email=user.email,
            user_full_name=user.full_name,
            client_id=client.client_id,
            scopes=authorization_code.scopes,
            expires_at=now + timedelta(seconds=client.access_token_validity_seconds),
            refresh_expires_at=now
            + timedelta(seconds=client.refresh_token_validity_seconds),
        )
    )
    session.commit()
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": client.access_token_validity_seconds,
        "scope": authorization_code.scopes or "",
    }


@router.post("/revoke", status_code=204)
def revoke_oauth2_protocol_token(
    session: SessionDep,
    token: str = Form(...),
    client_id: str = Form(...),
    client_secret: str | None = Form(default=None),
) -> Response:
    client = authenticate_protocol_client(
        session=session, client_id=client_id, client_secret=client_secret
    )
    token_hash = hash_oauth2_value(token)
    stored_token = session.exec(
        select(OAuth2AccessToken).where(
            OAuth2AccessToken.client_id == client.client_id,
            or_(
                OAuth2AccessToken.access_token_hash == token_hash,
                OAuth2AccessToken.refresh_token_hash == token_hash,
            ),
        )
    ).first()
    if stored_token and stored_token.revoked_at is None:
        revoke_token_family(session, stored_token.token_family_id)
        session.commit()
    return Response(status_code=204)


def mask_oauth2_client(client: OAuth2Client) -> OAuth2ClientPublic:
    data = OAuth2ClientPublic.model_validate(client)
    if data.client_secret:
        data.client_secret = "******"
    return data


def mask_oauth2_access_token(token: OAuth2AccessToken) -> OAuth2AccessTokenPublic:
    data = OAuth2AccessTokenPublic.model_validate(token)
    if data.access_token:
        data.access_token = "******"
    if data.refresh_token:
        data.refresh_token = "******"
    return data


def ensure_oauth2_client_id_unique(
    *, session: SessionDep, client_id: str, exclude_id: uuid.UUID | None = None
) -> None:
    statement = select(OAuth2Client).where(OAuth2Client.client_id == client_id)
    if exclude_id:
        statement = statement.where(OAuth2Client.id != exclude_id)
    if session.exec(statement).first():
        raise HTTPException(status_code=409, detail="OAuth2 client id already exists")


@router.get(
    "/clients",
    dependencies=[Depends(require_permission("system:oauth2-client:list"))],
    response_model=OAuth2ClientsPublic,
)
def read_oauth2_clients(
    session: SessionDep,
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    is_active: bool | None = None,
) -> Any:
    page, page_size = normalize_pagination(page=page, page_size=page_size)
    filters = []
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            or_(
                col(OAuth2Client.client_id).ilike(pattern),
                col(OAuth2Client.name).ilike(pattern),
                col(OAuth2Client.description).ilike(pattern),
            )
        )
    if is_active is not None:
        filters.append(OAuth2Client.is_active == is_active)

    count_statement = select(func.count()).select_from(OAuth2Client)
    if filters:
        count_statement = count_statement.where(*filters)
    count = session.exec(count_statement).one()

    statement = select(OAuth2Client)
    if filters:
        statement = statement.where(*filters)
    clients = session.exec(
        statement.order_by(col(OAuth2Client.updated_at).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return OAuth2ClientsPublic(
        items=[mask_oauth2_client(client) for client in clients],
        total=count,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/clients",
    dependencies=[Depends(require_permission("system:oauth2-client:create"))],
    response_model=OAuth2ClientPublic,
)
def create_oauth2_client(
    *, session: SessionDep, client_in: OAuth2ClientCreate
) -> OAuth2ClientPublic:
    ensure_oauth2_client_id_unique(session=session, client_id=client_in.client_id)
    client = OAuth2Client.model_validate(client_in)
    if client.client_secret:
        client.client_secret = encrypt_secret(client.client_secret)
    session.add(client)
    session.commit()
    session.refresh(client)
    return mask_oauth2_client(client)


@router.get(
    "/clients/{client_id}",
    dependencies=[Depends(require_permission("system:oauth2-client:list"))],
    response_model=OAuth2ClientPublic,
)
def read_oauth2_client(session: SessionDep, client_id: uuid.UUID) -> OAuth2ClientPublic:
    client = session.get(OAuth2Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="OAuth2 client not found")
    return mask_oauth2_client(client)


@router.patch(
    "/clients/{client_id}",
    dependencies=[Depends(require_permission("system:oauth2-client:update"))],
    response_model=OAuth2ClientPublic,
)
def update_oauth2_client(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    client_id: uuid.UUID,
    client_in: OAuth2ClientUpdate,
) -> OAuth2ClientPublic:
    client = session.get(OAuth2Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="OAuth2 client not found")

    update_data = client_in.model_dump(exclude_unset=True)
    current_password = update_data.pop("current_password", None)
    if "client_id" in update_data and update_data["client_id"] != client.client_id:
        ensure_oauth2_client_id_unique(
            session=session,
            client_id=update_data["client_id"],
            exclude_id=client.id,
        )
    if update_data.get("client_secret") == "******":
        update_data.pop("client_secret")
    elif update_data.get("client_secret"):
        if not current_password:
            raise HTTPException(status_code=400, detail="Current password is required")
        verified, _ = verify_password(current_password, current_user.hashed_password)
        if not verified:
            raise HTTPException(status_code=400, detail="Incorrect password")
        update_data["client_secret"] = encrypt_secret(update_data["client_secret"])

    client.sqlmodel_update(update_data)
    client.updated_at = get_datetime_utc()
    session.add(client)
    session.commit()
    session.refresh(client)
    return mask_oauth2_client(client)


@router.delete(
    "/clients/{client_id}",
    dependencies=[Depends(require_permission("system:oauth2-client:delete"))],
    status_code=204,
)
def delete_oauth2_client(session: SessionDep, client_id: uuid.UUID) -> None:
    client = session.get(OAuth2Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="OAuth2 client not found")
    active_token = session.exec(
        select(OAuth2AccessToken).where(
            OAuth2AccessToken.client_id == client.client_id,
            OAuth2AccessToken.revoked_at.is_(None),
            OAuth2AccessToken.expires_at > get_datetime_utc(),
        )
    ).first()
    if active_token:
        raise HTTPException(
            status_code=400,
            detail="OAuth2 client has active access tokens",
        )
    session.delete(client)
    session.commit()
    return None


@router.get(
    "/tokens",
    dependencies=[Depends(require_permission("system:oauth2-token:list"))],
    response_model=OAuth2AccessTokensPublic,
)
def read_oauth2_tokens(
    session: SessionDep,
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    client_id: str | None = None,
    user_id: uuid.UUID | None = None,
    revoked: bool | None = None,
) -> Any:
    page, page_size = normalize_pagination(page=page, page_size=page_size)
    filters = []
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            or_(
                col(OAuth2AccessToken.access_token).ilike(pattern),
                col(OAuth2AccessToken.refresh_token).ilike(pattern),
                col(OAuth2AccessToken.user_email).ilike(pattern),
                col(OAuth2AccessToken.user_full_name).ilike(pattern),
            )
        )
    if client_id:
        filters.append(col(OAuth2AccessToken.client_id).ilike(f"%{client_id}%"))
    if user_id:
        filters.append(OAuth2AccessToken.user_id == user_id)
    if revoked is not None:
        filters.append(
            OAuth2AccessToken.revoked_at.is_not(None)
            if revoked
            else OAuth2AccessToken.revoked_at.is_(None)
        )

    count_statement = select(func.count()).select_from(OAuth2AccessToken)
    if filters:
        count_statement = count_statement.where(*filters)
    count = session.exec(count_statement).one()

    statement = select(OAuth2AccessToken)
    if filters:
        statement = statement.where(*filters)
    tokens = session.exec(
        statement.order_by(col(OAuth2AccessToken.created_at).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return OAuth2AccessTokensPublic(
        items=[mask_oauth2_access_token(token) for token in tokens],
        total=count,
        page=page,
        page_size=page_size,
    )


@router.delete(
    "/tokens/{token_id}",
    dependencies=[Depends(require_permission("system:oauth2-token:delete"))],
    status_code=204,
)
def revoke_oauth2_token(session: SessionDep, token_id: uuid.UUID) -> Response:
    token = session.get(OAuth2AccessToken, token_id)
    if not token:
        raise HTTPException(status_code=404, detail="OAuth2 access token not found")
    if token.revoked_at is None:
        token.revoked_at = get_datetime_utc()
        session.add(token)
        session.commit()
    return Response(status_code=204)
