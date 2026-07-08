import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import col, delete, func, select

from app.api.deps import CurrentUser, SessionDep, require_permission
from app.models import (
    Menu,
    MenuCreate,
    MenuPublic,
    MenusPublic,
    MenuUpdate,
    RoleMenu,
    UserRole,
    get_datetime_utc,
)

router = APIRouter(prefix="/menus", tags=["menus"])


@router.get(
    "",
    dependencies=[Depends(require_permission("system:menu:list"))],
    response_model=MenusPublic,
)
def read_menus(
    session: SessionDep,
    page: int = 1,
    page_size: int = 200,
    keyword: str | None = None,
) -> Any:
    filters = []
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            (col(Menu.title).ilike(pattern))
            | (col(Menu.permission_code).ilike(pattern))
            | (col(Menu.route_path).ilike(pattern))
        )

    count_statement = select(func.count()).select_from(Menu)
    if filters:
        count_statement = count_statement.where(*filters)
    count = session.exec(count_statement).one()

    statement = select(Menu)
    if filters:
        statement = statement.where(*filters)
    statement = (
        statement.order_by(col(Menu.sort), col(Menu.created_at).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    menus = session.exec(statement).all()
    return MenusPublic(
        items=[MenuPublic.model_validate(menu) for menu in menus],
        total=count,
        page=page,
        page_size=page_size,
    )


@router.get("/me", response_model=list[MenuPublic])
def read_my_menus(session: SessionDep, current_user: CurrentUser) -> Any:
    if current_user.is_superuser:
        menus = session.exec(
            select(Menu)
            .where(Menu.is_active, Menu.is_visible)
            .order_by(col(Menu.sort), col(Menu.created_at))
        ).all()
    else:
        menus = session.exec(
            select(Menu)
            .join(RoleMenu, RoleMenu.menu_id == Menu.id)
            .join(UserRole, UserRole.role_id == RoleMenu.role_id)
            .where(
                UserRole.user_id == current_user.id,
                Menu.is_active,
                Menu.is_visible,
            )
            .order_by(col(Menu.sort), col(Menu.created_at))
        ).all()
    return [MenuPublic.model_validate(menu) for menu in menus]


@router.get("/permissions/me", response_model=list[str])
def read_my_permissions(session: SessionDep, current_user: CurrentUser) -> Any:
    if current_user.is_superuser:
        permissions = session.exec(
            select(Menu.permission_code).where(
                Menu.permission_code.is_not(None), Menu.is_active
            )
        ).all()
    else:
        permissions = session.exec(
            select(Menu.permission_code)
            .join(RoleMenu, RoleMenu.menu_id == Menu.id)
            .join(UserRole, UserRole.role_id == RoleMenu.role_id)
            .where(
                UserRole.user_id == current_user.id,
                Menu.permission_code.is_not(None),
                Menu.is_active,
            )
        ).all()
    return sorted({permission for permission in permissions if permission})


@router.post(
    "",
    dependencies=[Depends(require_permission("system:menu:create"))],
    response_model=MenuPublic,
)
def create_menu(*, session: SessionDep, menu_in: MenuCreate) -> Any:
    if menu_in.parent_id and not session.get(Menu, menu_in.parent_id):
        raise HTTPException(status_code=400, detail="Parent menu does not exist")
    if menu_in.permission_code:
        existing_menu = session.exec(
            select(Menu).where(Menu.permission_code == menu_in.permission_code)
        ).first()
        if existing_menu:
            raise HTTPException(status_code=409, detail="Permission code already exists")

    menu = Menu.model_validate(menu_in)
    session.add(menu)
    session.commit()
    session.refresh(menu)
    return menu


@router.patch(
    "/{menu_id}",
    dependencies=[Depends(require_permission("system:menu:update"))],
    response_model=MenuPublic,
)
def update_menu(
    *, session: SessionDep, menu_id: uuid.UUID, menu_in: MenuUpdate
) -> Any:
    menu = session.get(Menu, menu_id)
    if not menu:
        raise HTTPException(status_code=404, detail="Menu not found")
    if menu_in.parent_id == menu_id:
        raise HTTPException(status_code=400, detail="Menu cannot be its own parent")
    if menu_in.parent_id and not session.get(Menu, menu_in.parent_id):
        raise HTTPException(status_code=400, detail="Parent menu does not exist")
    if menu_in.permission_code and menu_in.permission_code != menu.permission_code:
        existing_menu = session.exec(
            select(Menu).where(Menu.permission_code == menu_in.permission_code)
        ).first()
        if existing_menu:
            raise HTTPException(status_code=409, detail="Permission code already exists")

    menu.sqlmodel_update(menu_in.model_dump(exclude_unset=True))
    menu.updated_at = get_datetime_utc()
    session.add(menu)
    session.commit()
    session.refresh(menu)
    return menu


@router.delete(
    "/{menu_id}",
    dependencies=[Depends(require_permission("system:menu:delete"))],
    status_code=204,
)
def delete_menu(*, session: SessionDep, menu_id: uuid.UUID) -> Response:
    menu = session.get(Menu, menu_id)
    if not menu:
        raise HTTPException(status_code=404, detail="Menu not found")

    child_menu = session.exec(select(Menu).where(Menu.parent_id == menu_id)).first()
    if child_menu:
        raise HTTPException(status_code=400, detail="Menu has child menus")

    session.exec(delete(RoleMenu).where(RoleMenu.menu_id == menu_id))
    session.delete(menu)
    session.commit()
    return Response(status_code=204)
