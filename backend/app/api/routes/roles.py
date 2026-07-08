import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import col, delete, func, select

from app.api.deps import SessionDep, require_permission
from app.models import (
    Menu,
    Role,
    RoleCreate,
    RoleMenu,
    RoleMenuUpdate,
    RolePublic,
    RolesPublic,
    RoleUpdate,
    UserRole,
    get_datetime_utc,
)

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get(
    "",
    dependencies=[Depends(require_permission("system:role:list"))],
    response_model=RolesPublic,
)
def read_roles(
    session: SessionDep,
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
) -> Any:
    filters = []
    if keyword:
        pattern = f"%{keyword}%"
        filters.append((col(Role.name).ilike(pattern)) | (col(Role.code).ilike(pattern)))

    count_statement = select(func.count()).select_from(Role)
    if filters:
        count_statement = count_statement.where(*filters)
    count = session.exec(count_statement).one()

    statement = select(Role)
    if filters:
        statement = statement.where(*filters)
    statement = (
        statement.order_by(col(Role.sort), col(Role.created_at).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    roles = session.exec(statement).all()
    return RolesPublic(
        items=[RolePublic.model_validate(role) for role in roles],
        total=count,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    dependencies=[Depends(require_permission("system:role:create"))],
    response_model=RolePublic,
)
def create_role(*, session: SessionDep, role_in: RoleCreate) -> Any:
    existing_role = session.exec(select(Role).where(Role.code == role_in.code)).first()
    if existing_role:
        raise HTTPException(status_code=409, detail="Role code already exists")

    role = Role.model_validate(role_in)
    session.add(role)
    session.commit()
    session.refresh(role)
    return role


@router.get(
    "/{role_id}",
    dependencies=[Depends(require_permission("system:role:list"))],
    response_model=RolePublic,
)
def read_role(*, session: SessionDep, role_id: uuid.UUID) -> Any:
    role = session.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


@router.patch(
    "/{role_id}",
    dependencies=[Depends(require_permission("system:role:update"))],
    response_model=RolePublic,
)
def update_role(
    *, session: SessionDep, role_id: uuid.UUID, role_in: RoleUpdate
) -> Any:
    role = session.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.is_system and role_in.is_system is False:
        raise HTTPException(status_code=400, detail="System role cannot be unmarked")
    if role_in.code and role_in.code != role.code:
        existing_role = session.exec(select(Role).where(Role.code == role_in.code)).first()
        if existing_role:
            raise HTTPException(status_code=409, detail="Role code already exists")

    role.sqlmodel_update(role_in.model_dump(exclude_unset=True))
    role.updated_at = get_datetime_utc()
    session.add(role)
    session.commit()
    session.refresh(role)
    return role


@router.delete(
    "/{role_id}",
    dependencies=[Depends(require_permission("system:role:delete"))],
    status_code=204,
)
def delete_role(*, session: SessionDep, role_id: uuid.UUID) -> Response:
    role = session.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.is_system:
        raise HTTPException(status_code=400, detail="System role cannot be deleted")

    bound_user = session.exec(
        select(UserRole).where(UserRole.role_id == role_id)
    ).first()
    if bound_user:
        raise HTTPException(status_code=400, detail="Role is assigned to users")

    session.exec(delete(RoleMenu).where(RoleMenu.role_id == role_id))
    session.delete(role)
    session.commit()
    return Response(status_code=204)


@router.get(
    "/{role_id}/menus",
    dependencies=[Depends(require_permission("system:role:list"))],
    response_model=list[uuid.UUID],
)
def read_role_menus(*, session: SessionDep, role_id: uuid.UUID) -> Any:
    role = session.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    role_menus = session.exec(
        select(RoleMenu).where(RoleMenu.role_id == role_id)
    ).all()
    return [role_menu.menu_id for role_menu in role_menus]


@router.put(
    "/{role_id}/menus",
    dependencies=[Depends(require_permission("system:role:update"))],
    response_model=list[uuid.UUID],
)
def update_role_menus(
    *, session: SessionDep, role_id: uuid.UUID, body: RoleMenuUpdate
) -> Any:
    role = session.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    if body.menu_ids:
        menus_count = session.exec(
            select(func.count()).select_from(Menu).where(col(Menu.id).in_(body.menu_ids))
        ).one()
        if menus_count != len(set(body.menu_ids)):
            raise HTTPException(status_code=400, detail="Some menus do not exist")

    session.exec(delete(RoleMenu).where(RoleMenu.role_id == role_id))
    for menu_id in set(body.menu_ids):
        session.add(RoleMenu(role_id=role_id, menu_id=menu_id))
    role.updated_at = get_datetime_utc()
    session.add(role)
    session.commit()
    return body.menu_ids
