import csv
import io
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlmodel import col, delete, func, or_, select

from app import crud
from app.api.deps import (
    CurrentTenant,
    CurrentUser,
    SessionDep,
    normalize_pagination,
    require_permission,
    user_has_permission,
)
from app.core.cache import CacheNamespace, redis_cache
from app.core.config import settings
from app.core.data_permissions import build_owner_data_scope_filter
from app.core.mfa import (
    build_totp_uri,
    decrypt_totp_secret,
    encrypt_totp_secret,
    generate_recovery_codes,
    generate_totp_secret,
    get_recovery_code_count,
    serialize_recovery_codes,
    verify_totp_code,
)
from app.core.quotas import ensure_member_quota
from app.core.security import get_password_hash, verify_password
from app.models import (
    Department,
    MasterDataAnonymizeRequest,
    Message,
    Post,
    PostPublic,
    Role,
    RolePublic,
    TenantMembership,
    UpdatePassword,
    User,
    UserCreate,
    UserMfaDisable,
    UserMfaEnable,
    UserMfaEnableResult,
    UserMfaSetup,
    UserMfaStatus,
    UserPost,
    UserPostUpdate,
    UserPublic,
    UserRole,
    UserRoleUpdate,
    UserSession,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
    get_datetime_utc,
)
from app.modules.outbox import enqueue_event
from app.utils import generate_new_account_email, send_email

router = APIRouter(prefix="/users", tags=["users"])


def ensure_user_is_mutable(user: User) -> None:
    if user.email.casefold() == str(settings.FIRST_SUPERUSER).casefold():
        raise HTTPException(
            status_code=403,
            detail="Built-in administrator cannot be modified",
        )


def parse_csv_bool(value: str | None, default: bool = False) -> bool:
    if value is None or value.strip() == "":
        return default
    normalized = value.strip().lower()
    return normalized in {"1", "true", "yes", "y", "启用", "是"}


def split_codes(value: str | None) -> list[str]:
    if not value:
        return []
    return [code.strip() for code in value.replace(";", ",").split(",") if code.strip()]


def resolve_department_id(
    session: SessionDep, tenant_id: uuid.UUID, code: str | None
) -> uuid.UUID | None:
    if not code:
        return None
    department = session.exec(
        select(Department).where(
            Department.tenant_id == tenant_id,
            Department.code == code,
        )
    ).first()
    if not department:
        raise ValueError(f"department code does not exist: {code}")
    return department.id


def resolve_roles(
    session: SessionDep, tenant_id: uuid.UUID, codes: list[str]
) -> list[Role]:
    if not codes:
        return []
    roles = session.exec(
        select(Role).where(
            Role.tenant_id == tenant_id,
            col(Role.code).in_(codes),
        )
    ).all()
    if len(roles) != len(set(codes)):
        found_codes = {role.code for role in roles}
        missing_codes = sorted(set(codes) - found_codes)
        raise ValueError(f"role codes do not exist: {', '.join(missing_codes)}")
    return roles


def resolve_posts(
    session: SessionDep, tenant_id: uuid.UUID, codes: list[str]
) -> list[Post]:
    if not codes:
        return []
    posts = session.exec(
        select(Post).where(
            Post.tenant_id == tenant_id,
            col(Post.code).in_(codes),
        )
    ).all()
    if len(posts) != len(set(codes)):
        found_codes = {post.code for post in posts}
        missing_codes = sorted(set(codes) - found_codes)
        raise ValueError(f"post codes do not exist: {', '.join(missing_codes)}")
    return posts


def get_user_role_codes(
    session: SessionDep, user_id: uuid.UUID, tenant_id: uuid.UUID
) -> str:
    roles = session.exec(
        select(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(
            UserRole.user_id == user_id,
            UserRole.tenant_id == tenant_id,
            Role.tenant_id == tenant_id,
        )
        .order_by(col(Role.sort), col(Role.created_at))
    ).all()
    return ",".join(role.code for role in roles)


def get_tenant_membership_or_404(
    session: SessionDep,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> TenantMembership:
    membership = session.exec(
        select(TenantMembership).where(
            TenantMembership.user_id == user_id,
            TenantMembership.tenant_id == tenant_id,
        )
    ).first()
    if membership is None:
        raise HTTPException(status_code=404, detail="User not found")
    return membership


def ensure_user_in_data_scope(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> TenantMembership:
    membership = get_tenant_membership_or_404(session, user_id, tenant_id)
    allowed = session.exec(
        select(User.id)
        .join(TenantMembership, TenantMembership.user_id == User.id)
        .where(
            User.id == user_id,
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.is_active,
            build_owner_data_scope_filter(
                session=session,
                current_user=current_user,
                tenant_id=tenant_id,
                owner_id_column=User.id,
            ),
        )
    ).first()
    if allowed is None:
        raise HTTPException(
            status_code=403,
            detail="The user is outside the current data scope",
        )
    return membership


def get_user_post_codes(
    session: SessionDep, user_id: uuid.UUID, tenant_id: uuid.UUID
) -> str:
    posts = session.exec(
        select(Post)
        .join(UserPost, UserPost.post_id == Post.id)
        .where(
            UserPost.user_id == user_id,
            UserPost.tenant_id == tenant_id,
            Post.tenant_id == tenant_id,
        )
        .order_by(col(Post.sort), col(Post.created_at))
    ).all()
    return ",".join(post.code for post in posts)


def build_user_public(user: User, membership: TenantMembership) -> UserPublic:
    return UserPublic.model_validate(
        user,
        update={"department_id": membership.department_id},
    )


def build_user_mfa_status(user: User) -> UserMfaStatus:
    pending_setup = bool(user.mfa_secret_encrypted and not user.mfa_enabled)
    return UserMfaStatus(
        enabled=user.mfa_enabled,
        pending_setup=pending_setup,
        method="totp" if user.mfa_enabled else None,
        confirmed_at=user.mfa_confirmed_at,
        recovery_codes_remaining=get_recovery_code_count(user.mfa_recovery_code_hashes),
    )


@router.get(
    "",
    dependencies=[Depends(require_permission("system:user:list"))],
    response_model=UsersPublic,
)
def read_users(
    session: SessionDep,
    current_user: CurrentUser,
    tenant_context: CurrentTenant,
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    department_id: uuid.UUID | None = None,
    is_active: bool | None = None,
) -> Any:
    """
    Retrieve users.
    """
    page, page_size = normalize_pagination(page=page, page_size=page_size)

    filters = [
        TenantMembership.tenant_id == tenant_context.tenant_id,
        TenantMembership.is_active,
        build_owner_data_scope_filter(
            session=session,
            current_user=current_user,
            tenant_id=tenant_context.tenant_id,
            owner_id_column=User.id,
        ),
    ]
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            or_(col(User.email).ilike(pattern), col(User.full_name).ilike(pattern))
        )
    if department_id:
        filters.append(TenantMembership.department_id == department_id)
    if is_active is not None:
        filters.append(User.is_active == is_active)

    count_statement = (
        select(func.count())
        .select_from(User)
        .join(TenantMembership, TenantMembership.user_id == User.id)
    )
    if filters:
        count_statement = count_statement.where(*filters)
    count = session.exec(count_statement).one()

    offset = (page - 1) * page_size
    statement = select(User, TenantMembership).join(
        TenantMembership, TenantMembership.user_id == User.id
    )
    if filters:
        statement = statement.where(*filters)
    statement = (
        statement.order_by(col(User.created_at).desc()).offset(offset).limit(page_size)
    )
    rows = session.exec(statement).all()

    users_public = [build_user_public(user, membership) for user, membership in rows]
    return UsersPublic(
        items=users_public,
        total=count,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    dependencies=[Depends(require_permission("system:user:create"))],
    response_model=UserPublic,
)
def create_user(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    tenant_context: CurrentTenant,
    user_in: UserCreate,
) -> Any:
    """
    Create new user.
    """
    user = crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )
    if user_in.mobile:
        user_in.mobile = user_in.mobile.strip()
        if crud.get_user_by_mobile(session=session, mobile=user_in.mobile):
            raise HTTPException(
                status_code=409,
                detail="User with this mobile already exists",
            )
    if user_in.is_superuser and not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    ensure_member_quota(
        session=session,
        tenant_id=tenant_context.tenant_id,
    )
    if user_in.department_id:
        department = session.exec(
            select(Department).where(
                Department.id == user_in.department_id,
                Department.tenant_id == tenant_context.tenant_id,
            )
        ).first()
        if department is None:
            raise HTTPException(status_code=400, detail="Department does not exist")

    user = crud.create_user(
        session=session,
        user_create=user_in,
        tenant_id=tenant_context.tenant_id,
    )
    if settings.emails_enabled and user_in.email:
        email_data = generate_new_account_email(
            email_to=user_in.email, username=user_in.email, password=user_in.password
        )
        send_email(
            email_to=user_in.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    membership = get_tenant_membership_or_404(
        session, user.id, tenant_context.tenant_id
    )
    return build_user_public(user, membership)


@router.patch("/me", response_model=UserPublic)
def update_user_me(
    *,
    session: SessionDep,
    user_in: UserUpdateMe,
    current_user: CurrentUser,
    tenant_context: CurrentTenant,
) -> Any:
    """
    Update own user.
    """

    if user_in.email:
        existing_user = crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )
    user_data = user_in.model_dump(exclude_unset=True)
    current_user.sqlmodel_update(user_data)
    current_user.updated_at = get_datetime_utc()
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    membership = get_tenant_membership_or_404(
        session, current_user.id, tenant_context.tenant_id
    )
    return build_user_public(current_user, membership)


@router.patch("/me/password", response_model=Message)
def update_password_me(
    *, session: SessionDep, body: UpdatePassword, current_user: CurrentUser
) -> Any:
    """
    Update own password.
    """
    verified, _ = verify_password(body.current_password, current_user.hashed_password)
    if not verified:
        raise HTTPException(status_code=400, detail="Incorrect password")
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=400, detail="New password cannot be the same as the current one"
        )
    hashed_password = get_password_hash(body.new_password)
    current_user.hashed_password = hashed_password
    current_user.updated_at = get_datetime_utc()
    crud.revoke_user_sessions(session=session, user_id=current_user.id)
    session.add(current_user)
    session.commit()
    return Message(message="Password updated successfully")


@router.get("/me", response_model=UserPublic)
def read_user_me(
    session: SessionDep,
    current_user: CurrentUser,
    tenant_context: CurrentTenant,
) -> Any:
    """
    Get current user.
    """
    membership = get_tenant_membership_or_404(
        session, current_user.id, tenant_context.tenant_id
    )
    return build_user_public(current_user, membership)


@router.get("/me/mfa", response_model=UserMfaStatus)
def read_user_mfa_status(current_user: CurrentUser) -> UserMfaStatus:
    """
    Get current user's MFA status.
    """
    return build_user_mfa_status(current_user)


@router.post("/me/mfa/setup", response_model=UserMfaSetup)
def setup_user_mfa(*, session: SessionDep, current_user: CurrentUser) -> UserMfaSetup:
    """
    Create or replace current user's pending TOTP setup.
    """
    if not settings.MFA_TOTP_ENABLED:
        raise HTTPException(status_code=404, detail="MFA is disabled")
    if current_user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA has already been enabled.")

    secret = generate_totp_secret()
    current_user.mfa_secret_encrypted = encrypt_totp_secret(secret)
    current_user.mfa_confirmed_at = None
    current_user.updated_at = get_datetime_utc()
    session.add(current_user)
    session.commit()

    return UserMfaSetup(
        secret=secret,
        otpauth_uri=build_totp_uri(secret=secret, account_name=current_user.email),
        issuer=settings.MFA_TOTP_ISSUER,
        account_name=current_user.email,
    )


@router.post("/me/mfa/enable", response_model=UserMfaEnableResult)
def enable_user_mfa(
    *, session: SessionDep, body: UserMfaEnable, current_user: CurrentUser
) -> UserMfaEnableResult:
    """
    Verify TOTP code and enable MFA for current user.
    """
    if not settings.MFA_TOTP_ENABLED:
        raise HTTPException(status_code=404, detail="MFA is disabled")
    if current_user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA has already been enabled.")
    if not current_user.mfa_secret_encrypted:
        raise HTTPException(status_code=400, detail="MFA is not configured.")

    try:
        secret = decrypt_totp_secret(current_user.mfa_secret_encrypted)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="MFA setup is invalid. Please restart MFA setup.",
        )

    if not verify_totp_code(secret=secret, code=body.code):
        raise HTTPException(status_code=400, detail="MFA verification code is invalid.")

    now = get_datetime_utc()
    recovery_codes = generate_recovery_codes()
    current_user.mfa_enabled = True
    current_user.mfa_recovery_code_hashes = serialize_recovery_codes(recovery_codes)
    current_user.mfa_confirmed_at = now
    current_user.updated_at = now
    session.add(current_user)
    session.commit()
    return UserMfaEnableResult(
        message="MFA enabled successfully",
        recovery_codes=recovery_codes,
    )


@router.post("/me/mfa/disable", response_model=Message)
def disable_user_mfa(
    *, session: SessionDep, body: UserMfaDisable, current_user: CurrentUser
) -> Message:
    """
    Disable MFA for current user after verifying password and TOTP code.
    """
    if not settings.MFA_TOTP_ENABLED:
        raise HTTPException(status_code=404, detail="MFA is disabled")
    if not current_user.mfa_enabled or not current_user.mfa_secret_encrypted:
        raise HTTPException(status_code=400, detail="MFA is not configured.")

    verified, _ = verify_password(body.current_password, current_user.hashed_password)
    if not verified:
        raise HTTPException(status_code=400, detail="Incorrect password")

    try:
        secret = decrypt_totp_secret(current_user.mfa_secret_encrypted)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="MFA setup is invalid. Please restart MFA setup.",
        )

    if not verify_totp_code(secret=secret, code=body.code):
        raise HTTPException(status_code=400, detail="MFA verification code is invalid.")

    current_user.mfa_enabled = False
    current_user.mfa_secret_encrypted = None
    current_user.mfa_recovery_code_hashes = None
    current_user.mfa_confirmed_at = None
    current_user.updated_at = get_datetime_utc()
    session.add(current_user)
    session.commit()
    return Message(message="MFA disabled successfully")


@router.post(
    "/{user_id}/mfa/reset",
    dependencies=[Depends(require_permission("system:user:update"))],
    response_model=Message,
)
def reset_user_mfa(
    session: SessionDep,
    current_user: CurrentUser,
    tenant_context: CurrentTenant,
    user_id: uuid.UUID,
) -> Message:
    """Reset a user's MFA after an administrator has verified the recovery request."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    ensure_user_in_data_scope(
        session=session,
        current_user=current_user,
        tenant_id=tenant_context.tenant_id,
        user_id=user_id,
    )
    ensure_user_is_mutable(user)

    user.mfa_enabled = False
    user.mfa_secret_encrypted = None
    user.mfa_recovery_code_hashes = None
    user.mfa_confirmed_at = None
    user.updated_at = get_datetime_utc()
    crud.revoke_user_sessions(session=session, user_id=user.id)
    session.add(user)
    session.commit()
    return Message(message="MFA reset successfully")


@router.get(
    "/export",
    dependencies=[Depends(require_permission("system:user:list"))],
)
def export_users(
    session: SessionDep,
    current_user: CurrentUser,
    tenant_context: CurrentTenant,
) -> StreamingResponse:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "email",
            "full_name",
            "is_active",
            "is_superuser",
            "department_id",
            "department_code",
            "role_codes",
            "post_codes",
            "created_at",
        ]
    )
    rows = session.exec(
        select(User, TenantMembership)
        .join(TenantMembership, TenantMembership.user_id == User.id)
        .where(
            TenantMembership.tenant_id == tenant_context.tenant_id,
            TenantMembership.is_active,
            build_owner_data_scope_filter(
                session=session,
                current_user=current_user,
                tenant_id=tenant_context.tenant_id,
                owner_id_column=User.id,
            ),
        )
        .order_by(col(User.created_at).desc())
    ).all()
    for user, membership in rows:
        department_code = ""
        if membership.department_id:
            department = session.exec(
                select(Department).where(
                    Department.id == membership.department_id,
                    Department.tenant_id == tenant_context.tenant_id,
                )
            ).first()
            department_code = department.code if department else ""
        writer.writerow(
            [
                user.id,
                user.email,
                user.full_name or "",
                user.is_active,
                user.is_superuser,
                membership.department_id or "",
                department_code,
                get_user_role_codes(session, user.id, tenant_context.tenant_id),
                get_user_post_codes(session, user.id, tenant_context.tenant_id),
                user.created_at or "",
            ]
        )
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="users.csv"'},
    )


@router.get(
    "/import-template",
    dependencies=[Depends(require_permission("system:user:create"))],
)
def download_user_import_template() -> StreamingResponse:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "email",
            "password",
            "full_name",
            "department_code",
            "role_codes",
            "post_codes",
            "is_active",
            "is_superuser",
        ]
    )
    writer.writerow(
        [
            "user@example.com",
            "changethis",
            "示例用户",
            "headquarters",
            "user",
            "developer",
            "true",
            "false",
        ]
    )
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="users-import-template.csv"'
        },
    )


@router.post(
    "/import",
    dependencies=[Depends(require_permission("system:user:create"))],
)
async def import_users(
    session: SessionDep,
    current_user: CurrentUser,
    tenant_context: CurrentTenant,
    file: UploadFile = File(...),
) -> dict[str, Any]:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    raw_content = await file.read()
    try:
        content = raw_content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV file must be UTF-8 encoded")

    reader = csv.DictReader(io.StringIO(content))
    required_fields = {"email", "password"}
    if not reader.fieldnames or not required_fields <= set(reader.fieldnames):
        raise HTTPException(
            status_code=400, detail="CSV must contain email and password columns"
        )

    success_count = 0
    errors: list[dict[str, Any]] = []
    seen_emails: set[str] = set()
    for row_number, row in enumerate(reader, start=2):
        email = (row.get("email") or "").strip().lower()
        password = row.get("password") or ""
        role_codes = split_codes(row.get("role_codes"))
        post_codes = split_codes(row.get("post_codes"))
        try:
            if not email:
                raise ValueError("email is required")
            if email in seen_emails:
                raise ValueError("email is duplicated in CSV")
            seen_emails.add(email)
            if crud.get_user_by_email(session=session, email=email):
                raise ValueError("email already exists")

            ensure_member_quota(
                session=session,
                tenant_id=tenant_context.tenant_id,
            )

            is_superuser = parse_csv_bool(row.get("is_superuser"), default=False)
            if is_superuser and not current_user.is_superuser:
                raise ValueError("not allowed to import superuser")

            department_id = resolve_department_id(
                session,
                tenant_context.tenant_id,
                (row.get("department_code") or "").strip() or None,
            )
            roles = resolve_roles(session, tenant_context.tenant_id, role_codes)
            posts = resolve_posts(session, tenant_context.tenant_id, post_codes)
            user_in = UserCreate(
                email=email,
                password=password,
                full_name=(row.get("full_name") or "").strip() or None,
                department_id=department_id,
                is_active=parse_csv_bool(row.get("is_active"), default=True),
                is_superuser=is_superuser,
            )
            user = crud.create_user(
                session=session,
                user_create=user_in,
                tenant_id=tenant_context.tenant_id,
            )

            if role_codes:
                session.exec(
                    delete(UserRole).where(
                        UserRole.user_id == user.id,
                        UserRole.tenant_id == tenant_context.tenant_id,
                    )
                )
                for role in roles:
                    session.add(
                        UserRole(
                            user_id=user.id,
                            role_id=role.id,
                            tenant_id=tenant_context.tenant_id,
                        )
                    )
            for post in posts:
                session.add(
                    UserPost(
                        user_id=user.id,
                        post_id=post.id,
                        tenant_id=tenant_context.tenant_id,
                    )
                )
            session.commit()
            if role_codes:
                redis_cache.bump_namespace(CacheNamespace.RBAC)
            success_count += 1
        except (ValidationError, ValueError) as exc:
            session.rollback()
            errors.append({"row": row_number, "error": str(exc)})

    return {
        "errors": errors,
        "failed": len(errors),
        "success": success_count,
        "total": success_count + len(errors),
    }


@router.get("/{user_id}", response_model=UserPublic)
def read_user_by_id(
    user_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    tenant_context: CurrentTenant,
) -> Any:
    """
    Get a specific user by id.
    """
    if user_id == current_user.id:
        membership = get_tenant_membership_or_404(
            session, user_id, tenant_context.tenant_id
        )
        return build_user_public(current_user, membership)
    if not user_has_permission(
        session=session,
        current_user=current_user,
        tenant_id=tenant_context.tenant_id,
        permission_code="system:user:list",
    ):
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have enough privileges",
        )
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    membership = ensure_user_in_data_scope(
        session=session,
        current_user=current_user,
        tenant_id=tenant_context.tenant_id,
        user_id=user_id,
    )
    return build_user_public(user, membership)


@router.get(
    "/{user_id}/roles",
    dependencies=[Depends(require_permission("system:user:list"))],
    response_model=list[RolePublic],
)
def read_user_roles(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    tenant_context: CurrentTenant,
    user_id: uuid.UUID,
) -> Any:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    ensure_user_in_data_scope(
        session=session,
        current_user=current_user,
        tenant_id=tenant_context.tenant_id,
        user_id=user_id,
    )
    roles = session.exec(
        select(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(
            UserRole.user_id == user_id, UserRole.tenant_id == tenant_context.tenant_id
        )
        .order_by(col(Role.sort), col(Role.created_at))
    ).all()
    return [RolePublic.model_validate(role) for role in roles]


@router.put(
    "/{user_id}/roles",
    dependencies=[Depends(require_permission("system:user:update"))],
    response_model=list[uuid.UUID],
)
def update_user_roles(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    tenant_context: CurrentTenant,
    user_id: uuid.UUID,
    body: UserRoleUpdate,
) -> Any:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    ensure_user_in_data_scope(
        session=session,
        current_user=current_user,
        tenant_id=tenant_context.tenant_id,
        user_id=user_id,
    )
    ensure_user_is_mutable(user)
    if body.role_ids:
        role_count = session.exec(
            select(func.count())
            .select_from(Role)
            .where(
                Role.tenant_id == tenant_context.tenant_id,
                col(Role.id).in_(body.role_ids),
            )
        ).one()
        if role_count != len(set(body.role_ids)):
            raise HTTPException(status_code=400, detail="Some roles do not exist")

    session.exec(
        delete(UserRole).where(
            UserRole.user_id == user_id, UserRole.tenant_id == tenant_context.tenant_id
        )
    )
    for role_id in set(body.role_ids):
        session.add(
            UserRole(
                user_id=user_id, role_id=role_id, tenant_id=tenant_context.tenant_id
            )
        )
    user.updated_at = get_datetime_utc()
    session.add(user)
    session.commit()
    redis_cache.bump_namespace(CacheNamespace.RBAC)
    return body.role_ids


@router.get(
    "/{user_id}/posts",
    dependencies=[Depends(require_permission("system:user:list"))],
    response_model=list[PostPublic],
)
def read_user_posts(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    tenant_context: CurrentTenant,
    user_id: uuid.UUID,
) -> Any:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    ensure_user_in_data_scope(
        session=session,
        current_user=current_user,
        tenant_id=tenant_context.tenant_id,
        user_id=user_id,
    )
    posts = session.exec(
        select(Post)
        .join(UserPost, UserPost.post_id == Post.id)
        .where(UserPost.user_id == user_id)
        .where(
            UserPost.tenant_id == tenant_context.tenant_id,
            Post.tenant_id == tenant_context.tenant_id,
        )
        .order_by(col(Post.sort), col(Post.created_at))
    ).all()
    return [PostPublic.model_validate(post) for post in posts]


@router.put(
    "/{user_id}/posts",
    dependencies=[Depends(require_permission("system:user:update"))],
    response_model=list[uuid.UUID],
)
def update_user_posts(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    tenant_context: CurrentTenant,
    user_id: uuid.UUID,
    body: UserPostUpdate,
) -> Any:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    ensure_user_in_data_scope(
        session=session,
        current_user=current_user,
        tenant_id=tenant_context.tenant_id,
        user_id=user_id,
    )
    if body.post_ids:
        post_count = session.exec(
            select(func.count())
            .select_from(Post)
            .where(
                Post.tenant_id == tenant_context.tenant_id,
                col(Post.id).in_(body.post_ids),
            )
        ).one()
        if post_count != len(set(body.post_ids)):
            raise HTTPException(status_code=400, detail="Some posts do not exist")
    ensure_user_is_mutable(user)

    session.exec(
        delete(UserPost).where(
            UserPost.user_id == user_id,
            UserPost.tenant_id == tenant_context.tenant_id,
        )
    )
    for post_id in set(body.post_ids):
        session.add(
            UserPost(
                user_id=user_id,
                post_id=post_id,
                tenant_id=tenant_context.tenant_id,
            )
        )
    user.updated_at = get_datetime_utc()
    session.add(user)
    session.commit()
    return body.post_ids


@router.patch(
    "/{user_id}",
    dependencies=[Depends(require_permission("system:user:update"))],
    response_model=UserPublic,
)
def update_user(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    tenant_context: CurrentTenant,
    user_id: uuid.UUID,
    user_in: UserUpdate,
) -> Any:
    """
    Update a user.
    """

    db_user = session.get(User, user_id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )
    membership = ensure_user_in_data_scope(
        session=session,
        current_user=current_user,
        tenant_id=tenant_context.tenant_id,
        user_id=user_id,
    )
    # The built-in administrator's identity is protected, while its
    # tenant-specific department assignment remains administrable per tenant.
    if user_in.model_fields_set - {"department_id"}:
        ensure_user_is_mutable(db_user)
    if db_user.is_superuser and not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    if user_in.is_superuser is not None and not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    if user_in.email:
        existing_user = crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )
    if user_in.mobile:
        user_in.mobile = user_in.mobile.strip()
        existing_user = crud.get_user_by_mobile(
            session=session,
            mobile=user_in.mobile,
        )
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=409,
                detail="User with this mobile already exists",
            )
    if db_user.is_superuser and user_in.is_superuser is False:
        superuser_count = session.exec(
            select(func.count())
            .select_from(User)
            .where(User.is_superuser, User.id != user_id)
        ).one()
        if superuser_count == 0:
            raise HTTPException(
                status_code=400,
                detail="Cannot remove the last superuser",
            )

    if user_in.department_id is not None:
        department = session.exec(
            select(Department).where(
                Department.id == user_in.department_id,
                Department.tenant_id == tenant_context.tenant_id,
            )
        ).first()
        if department is None:
            raise HTTPException(status_code=400, detail="Department does not exist")
        membership.department_id = user_in.department_id
        session.add(membership)
    elif "department_id" in user_in.model_fields_set:
        membership.department_id = None
        session.add(membership)

    db_user = crud.update_user(session=session, db_user=db_user, user_in=user_in)
    if user_in.is_superuser is not None:
        redis_cache.bump_namespace(CacheNamespace.RBAC)
    return build_user_public(db_user, membership)


@router.delete(
    "/{user_id}",
    dependencies=[Depends(require_permission("system:user:delete"))],
    status_code=204,
)
def delete_user(
    session: SessionDep,
    current_user: CurrentUser,
    tenant_context: CurrentTenant,
    user_id: uuid.UUID,
) -> None:
    """
    Delete a user.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    membership = ensure_user_in_data_scope(
        session=session,
        current_user=current_user,
        tenant_id=tenant_context.tenant_id,
        user_id=user_id,
    )
    ensure_user_is_mutable(user)
    if user == current_user:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    if user.is_superuser and not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    if user.is_superuser:
        superuser_count = session.exec(
            select(func.count()).select_from(User).where(User.is_superuser)
        ).one()
        if superuser_count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the last superuser",
            )
    memberships_count = session.exec(
        select(func.count())
        .select_from(TenantMembership)
        .where(TenantMembership.user_id == user_id)
    ).one()
    session.exec(
        delete(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.tenant_id == tenant_context.tenant_id,
        )
    )
    was_default = membership.is_default
    membership.is_active = False
    membership.is_default = False
    session.add(membership)
    if memberships_count > 1:
        if was_default:
            next_membership = session.exec(
                select(TenantMembership)
                .where(
                    TenantMembership.user_id == user_id,
                    TenantMembership.tenant_id != tenant_context.tenant_id,
                    TenantMembership.is_active,
                )
                .order_by(col(TenantMembership.created_at))
            ).first()
            if next_membership is not None:
                next_membership.is_default = True
                session.add(next_membership)
    else:
        user.is_active = False
        user.archived_at = get_datetime_utc()
        session.add(user)
    enqueue_event(
        session=session,
        module_code="platform",
        event_type="platform.user.archived",
        tenant_id=tenant_context.tenant_id,
        aggregate_id=str(user.id),
        payload={
            "user_id": str(user.id),
            "tenant_id": str(tenant_context.tenant_id),
            "full_name": user.full_name,
        },
    )
    session.commit()
    return None


@router.post(
    "/{user_id}/anonymize",
    dependencies=[Depends(require_permission("system:user:delete"))],
    response_model=UserPublic,
)
def anonymize_user(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    tenant_context: CurrentTenant,
    user_id: uuid.UUID,
    body: MasterDataAnonymizeRequest,
) -> UserPublic:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    ensure_user_in_data_scope(
        session=session,
        current_user=current_user,
        tenant_id=tenant_context.tenant_id,
        user_id=user_id,
    )
    ensure_user_is_mutable(user)
    now = get_datetime_utc()
    user.email = f"anonymous-{user.id}@invalid.local"
    user.mobile = None
    user.full_name = "Anonymous"
    user.avatar_url = None
    user.is_active = False
    user.archived_at = user.archived_at or now
    user.anonymized_at = now
    user.updated_at = now
    session.add(user)
    enqueue_event(
        session=session,
        module_code="platform",
        event_type="platform.user.anonymized",
        tenant_id=tenant_context.tenant_id,
        aggregate_id=str(user.id),
        payload={
            "user_id": str(user.id),
            "tenant_id": str(tenant_context.tenant_id),
            "reason": body.reason,
        },
    )
    session.commit()
    session.refresh(user)
    return UserPublic.model_validate(user)
