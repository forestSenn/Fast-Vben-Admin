import csv
import io
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import col, delete, func, or_, select

from app import crud
from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
    require_permission,
)
from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.models import (
    Item,
    Message,
    Role,
    RolePublic,
    UpdatePassword,
    User,
    UserCreate,
    UserPublic,
    UserRole,
    UserRoleUpdate,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
    get_datetime_utc,
)
from app.utils import generate_new_account_email, send_email

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UsersPublic,
)
def read_users(
    session: SessionDep, page: int = 1, page_size: int = 20, keyword: str | None = None
) -> Any:
    """
    Retrieve users.
    """

    filters = []
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            or_(col(User.email).ilike(pattern), col(User.full_name).ilike(pattern))
        )

    count_statement = select(func.count()).select_from(User)
    if filters:
        count_statement = count_statement.where(*filters)
    count = session.exec(count_statement).one()

    offset = (page - 1) * page_size
    statement = select(User)
    if filters:
        statement = statement.where(*filters)
    statement = statement.order_by(col(User.created_at).desc()).offset(offset).limit(page_size)
    users = session.exec(statement).all()

    users_public = [UserPublic.model_validate(user) for user in users]
    return UsersPublic(
        items=users_public,
        total=count,
        page=page,
        page_size=page_size,
    )


@router.post(
    "", dependencies=[Depends(get_current_active_superuser)], response_model=UserPublic
)
def create_user(*, session: SessionDep, user_in: UserCreate) -> Any:
    """
    Create new user.
    """
    user = crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )

    user = crud.create_user(session=session, user_create=user_in)
    if settings.emails_enabled and user_in.email:
        email_data = generate_new_account_email(
            email_to=user_in.email, username=user_in.email, password=user_in.password
        )
        send_email(
            email_to=user_in.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    return user


@router.patch("/me", response_model=UserPublic)
def update_user_me(
    *, session: SessionDep, user_in: UserUpdateMe, current_user: CurrentUser
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
    return current_user


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
    session.add(current_user)
    session.commit()
    return Message(message="Password updated successfully")


@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user.
    """
    return current_user


@router.get(
    "/export",
    dependencies=[Depends(require_permission("system:user:list"))],
)
def export_users(session: SessionDep) -> StreamingResponse:
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
            "created_at",
        ]
    )
    users = session.exec(select(User).order_by(col(User.created_at).desc())).all()
    for user in users:
        writer.writerow(
            [
                user.id,
                user.email,
                user.full_name or "",
                user.is_active,
                user.is_superuser,
                user.department_id or "",
                user.created_at or "",
            ]
        )
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="users.csv"'},
    )


@router.get("/{user_id}", response_model=UserPublic)
def read_user_by_id(
    user_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> Any:
    """
    Get a specific user by id.
    """
    user = session.get(User, user_id)
    if user == current_user:
        return user
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have enough privileges",
        )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get(
    "/{user_id}/roles",
    dependencies=[Depends(require_permission("system:user:list"))],
    response_model=list[RolePublic],
)
def read_user_roles(*, session: SessionDep, user_id: uuid.UUID) -> Any:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    roles = session.exec(
        select(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
        .order_by(col(Role.sort), col(Role.created_at))
    ).all()
    return [RolePublic.model_validate(role) for role in roles]


@router.put(
    "/{user_id}/roles",
    dependencies=[Depends(require_permission("system:user:update"))],
    response_model=list[uuid.UUID],
)
def update_user_roles(
    *, session: SessionDep, user_id: uuid.UUID, body: UserRoleUpdate
) -> Any:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.role_ids:
        role_count = session.exec(
            select(func.count()).select_from(Role).where(col(Role.id).in_(body.role_ids))
        ).one()
        if role_count != len(set(body.role_ids)):
            raise HTTPException(status_code=400, detail="Some roles do not exist")

    session.exec(delete(UserRole).where(UserRole.user_id == user_id))
    for role_id in set(body.role_ids):
        session.add(UserRole(user_id=user_id, role_id=role_id))
    user.updated_at = get_datetime_utc()
    session.add(user)
    session.commit()
    return body.role_ids


@router.patch(
    "/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
)
def update_user(
    *,
    session: SessionDep,
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
    if user_in.email:
        existing_user = crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
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

    db_user = crud.update_user(session=session, db_user=db_user, user_in=user_in)
    return db_user


@router.delete(
    "/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    status_code=204,
)
def delete_user(
    session: SessionDep, current_user: CurrentUser, user_id: uuid.UUID
) -> None:
    """
    Delete a user.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user == current_user:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
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
    statement = delete(Item).where(col(Item.owner_id) == user_id)
    session.exec(statement)
    session.delete(user)
    session.commit()
    return None
