import uuid
from collections.abc import Generator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session, select

from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.core.tenancy import (
    DEFAULT_TENANT_ID,
    TenantContext,
    get_active_tenant_membership,
    get_default_tenant,
)
from app.models import (
    Menu,
    Role,
    RoleMenu,
    TokenPayload,
    User,
    UserRole,
    UserSession,
    get_datetime_utc,
)

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)
optional_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token",
    auto_error=False,
)


def get_db() -> Generator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]
OptionalTokenDep = Annotated[str | None, Depends(optional_oauth2)]


def get_token_payload(token: TokenDep) -> TokenPayload:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        return TokenPayload(**payload)
    except InvalidTokenError, ValidationError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )


CurrentTokenPayload = Annotated[TokenPayload, Depends(get_token_payload)]


def get_current_user(session: SessionDep, token_data: CurrentTokenPayload) -> User:
    return get_user_from_token_payload(session=session, token_data=token_data)


def get_user_from_token_payload(*, session: Session, token_data: TokenPayload) -> User:
    if not token_data.sub or not token_data.jti:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    user = session.get(User, token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Inactive user")

    now = get_datetime_utc()
    user_session = session.exec(
        select(UserSession).where(
            UserSession.user_id == user.id,
            UserSession.token_jti == token_data.jti,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
    ).first()
    if not user_session:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    if token_data.tenant_id and token_data.tenant_id != user_session.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant context is invalid",
        )

    user_session.last_active_at = now
    session.add(user_session)
    session.commit()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_tenant_context(
    session: SessionDep,
    current_user: CurrentUser,
    token_data: CurrentTokenPayload,
) -> TenantContext:
    if not token_data.jti:
        raise HTTPException(status_code=403, detail="Tenant context is invalid")
    user_session = session.exec(
        select(UserSession).where(
            UserSession.user_id == current_user.id,
            UserSession.token_jti == token_data.jti,
            UserSession.revoked_at.is_(None),
        )
    ).first()
    if user_session is None:
        raise HTTPException(status_code=403, detail="Tenant context is invalid")
    tenant_id = token_data.tenant_id or user_session.tenant_id
    if tenant_id != user_session.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context is invalid")
    membership = get_active_tenant_membership(
        session=session,
        user_id=current_user.id,
        tenant_id=tenant_id,
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="Tenant context is invalid")
    _, tenant = membership
    return TenantContext(
        tenant_id=tenant.id,
        tenant_code=tenant.code,
        user_id=current_user.id,
    )


CurrentTenant = Annotated[TenantContext, Depends(get_current_tenant_context)]


def get_public_tenant_id(session: SessionDep, token: OptionalTokenDep) -> uuid.UUID:
    if token is None:
        tenant = get_default_tenant(session)
        return tenant.id if tenant is not None else DEFAULT_TENANT_ID
    try:
        token_data = TokenPayload(
            **jwt.decode(token, settings.SECRET_KEY, algorithms=[security.ALGORITHM])
        )
    except InvalidTokenError, ValidationError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    current_user = get_user_from_token_payload(
        session=session,
        token_data=token_data,
    )
    return get_current_tenant_context(
        session=session,
        current_user=current_user,
        token_data=token_data,
    ).tenant_id


PublicTenantId = Annotated[uuid.UUID, Depends(get_public_tenant_id)]


def get_optional_tenant_id(
    session: SessionDep, token: OptionalTokenDep
) -> uuid.UUID | None:
    if token is None:
        return None
    return get_public_tenant_id(session=session, token=token)


OptionalTenantId = Annotated[uuid.UUID | None, Depends(get_optional_tenant_id)]


def get_optional_current_user(
    session: SessionDep, token: OptionalTokenDep
) -> User | None:
    if not token:
        return None
    try:
        token_data = TokenPayload(
            **jwt.decode(token, settings.SECRET_KEY, algorithms=[security.ALGORITHM])
        )
    except InvalidTokenError, ValidationError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    return get_user_from_token_payload(session=session, token_data=token_data)


OptionalCurrentUser = Annotated[User | None, Depends(get_optional_current_user)]


def normalize_pagination(
    *, page: int, page_size: int, max_page_size: int = 100
) -> tuple[int, int]:
    if page < 1:
        raise HTTPException(status_code=422, detail="page must be greater than 0")
    if page_size < 1:
        raise HTTPException(status_code=422, detail="page_size must be greater than 0")
    return page, min(page_size, max_page_size)


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user


def user_has_permission(
    *,
    session: Session,
    current_user: User,
    tenant_id: uuid.UUID,
    permission_code: str,
) -> bool:
    if current_user.is_superuser:
        return True

    statement = (
        select(Menu)
        .join(RoleMenu, RoleMenu.menu_id == Menu.id)
        .join(Role, Role.id == RoleMenu.role_id)
        .join(UserRole, UserRole.role_id == RoleMenu.role_id)
        .where(
            UserRole.user_id == current_user.id,
            UserRole.tenant_id == tenant_id,
            Role.tenant_id == tenant_id,
            Menu.permission_code == permission_code,
            Menu.is_active,
            Role.is_active,
        )
    )
    return session.exec(statement).first() is not None


def require_permission(permission_code: str):
    def dependency(
        session: SessionDep,
        current_user: CurrentUser,
        tenant_context: CurrentTenant,
    ) -> User:
        if user_has_permission(
            session=session,
            current_user=current_user,
            tenant_id=tenant_context.tenant_id,
            permission_code=permission_code,
        ):
            return current_user

        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )

    return dependency
