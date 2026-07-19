import uuid
from typing import Any

from sqlmodel import Session, select

from app.core.security import get_password_hash, verify_password
from app.core.tenancy import add_user_to_tenant, get_default_tenant
from app.models import (
    Role,
    User,
    UserCreate,
    UserRole,
    UserSession,
    UserUpdate,
    get_datetime_utc,
)


def create_user(
    *,
    session: Session,
    user_create: UserCreate,
    tenant_id: uuid.UUID | None = None,
) -> User:
    db_obj = User(
        **user_create.model_dump(exclude={"department_id", "password"}),
        hashed_password=get_password_hash(user_create.password),
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    if tenant_id is None:
        default_tenant = get_default_tenant(session)
        tenant_id = default_tenant.id if default_tenant else None
    if tenant_id is not None:
        add_user_to_tenant(
            session=session,
            user_id=db_obj.id,
            tenant_id=tenant_id,
            is_default=True,
            department_id=user_create.department_id,
        )
    default_role = session.exec(
        select(Role).where(Role.tenant_id == tenant_id, Role.code == "user")
    ).first()
    if default_role and not db_obj.is_superuser:
        session.add(
            UserRole(
                user_id=db_obj.id,
                role_id=default_role.id,
                tenant_id=default_role.tenant_id,
            )
        )
    session.commit()
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
    user_data = user_in.model_dump(exclude_unset=True, exclude={"department_id"})
    extra_data = {}
    if "password" in user_data:
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    extra_data["updated_at"] = get_datetime_utc()
    db_user.sqlmodel_update(user_data, update=extra_data)
    if "password" in user_data:
        revoke_user_sessions(session=session, user_id=db_user.id)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user

def revoke_user_sessions(*, session: Session, user_id: uuid.UUID) -> None:
    revoked_at = get_datetime_utc()
    user_sessions = session.exec(
        select(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
        )
    ).all()
    for user_session in user_sessions:
        user_session.revoked_at = revoked_at
        session.add(user_session)


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    session_user = session.exec(statement).first()
    return session_user


def get_user_by_mobile(*, session: Session, mobile: str) -> User | None:
    return session.exec(select(User).where(User.mobile == mobile)).first()


# Dummy hash to use for timing attack prevention when user is not found
# This is an Argon2 hash of a random password, used to ensure constant-time comparison
DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$MjQyZWE1MzBjYjJlZTI0Yw$YTU4NGM5ZTZmYjE2NzZlZjY0ZWY3ZGRkY2U2OWFjNjk"


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        # Prevent timing attacks by running password verification even when user doesn't exist
        # This ensures the response time is similar whether or not the email exists
        verify_password(password, DUMMY_HASH)
        return None
    verified, updated_password_hash = verify_password(password, db_user.hashed_password)
    if not verified:
        return None
    if updated_password_hash:
        db_user.hashed_password = updated_password_hash
        db_user.updated_at = get_datetime_utc()
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
    return db_user
