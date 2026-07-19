import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import col, delete, func, select

from app.api.deps import (
    CurrentTenant,
    CurrentUser,
    SessionDep,
    normalize_pagination,
    require_permission,
)
from app.core.cache import CacheNamespace, redis_cache
from app.models import (
    Menu,
    MenuCreate,
    MenuPublic,
    MenusPublic,
    MenuUpdate,
    Role,
    RoleMenu,
    UserRole,
    get_datetime_utc,
)
from app.modules.access import filter_module_scoped_permissions

router = APIRouter(prefix="/menus", tags=["menus"])


def is_descendant_menu(
    *, session: SessionDep, menu_id: uuid.UUID, possible_descendant_id: uuid.UUID
) -> bool:
    current_id: uuid.UUID | None = possible_descendant_id
    visited: set[uuid.UUID] = set()
    while current_id:
        if current_id == menu_id:
            return True
        if current_id in visited:
            return True
        visited.add(current_id)
        current = session.get(Menu, current_id)
        current_id = current.parent_id if current else None
    return False


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
    page, page_size = normalize_pagination(
        page=page, page_size=page_size, max_page_size=500
    )
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
def read_my_menus(
    session: SessionDep,
    current_user: CurrentUser,
    tenant_context: CurrentTenant,
) -> Any:
    cache_subject = "superuser" if current_user.is_superuser else current_user.id
    cache_key = redis_cache.build_versioned_key(
        CacheNamespace.RBAC,
        "menus",
        tenant_context.tenant_id,
        cache_subject,
    )
    cached_menus = redis_cache.get_json(cache_key)
    if cached_menus is not None:
        return [MenuPublic.model_validate(menu) for menu in cached_menus]

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
            .join(Role, Role.id == RoleMenu.role_id)
            .join(UserRole, UserRole.role_id == RoleMenu.role_id)
            .where(
                UserRole.user_id == current_user.id,
                UserRole.tenant_id == tenant_context.tenant_id,
                Role.tenant_id == tenant_context.tenant_id,
                Menu.is_active,
                Menu.is_visible,
                Role.is_active,
            )
            .order_by(col(Menu.sort), col(Menu.created_at))
        ).all()
    visible_permission_codes = set(
        filter_module_scoped_permissions(
            session=session,
            tenant_id=tenant_context.tenant_id,
            permission_codes=[
                menu.permission_code for menu in menus if menu.permission_code is not None
            ],
        )
    )
    menus_public = [
        MenuPublic.model_validate(menu)
        for menu in menus
        if menu.permission_code is None or menu.permission_code in visible_permission_codes
    ]
    redis_cache.set_json(
        cache_key,
        [menu.model_dump(mode="json") for menu in menus_public],
    )
    return menus_public


@router.get("/permissions/me", response_model=list[str])
def read_my_permissions(
    session: SessionDep,
    current_user: CurrentUser,
    tenant_context: CurrentTenant,
) -> Any:
    cache_subject = "superuser" if current_user.is_superuser else current_user.id
    cache_key = redis_cache.build_versioned_key(
        CacheNamespace.RBAC,
        "permissions",
        tenant_context.tenant_id,
        cache_subject,
    )
    cached_permissions = redis_cache.get_json(cache_key)
    if cached_permissions is not None:
        return [str(permission) for permission in cached_permissions]

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
            .join(Role, Role.id == RoleMenu.role_id)
            .join(UserRole, UserRole.role_id == RoleMenu.role_id)
            .where(
                UserRole.user_id == current_user.id,
                UserRole.tenant_id == tenant_context.tenant_id,
                Role.tenant_id == tenant_context.tenant_id,
                Menu.permission_code.is_not(None),
                Menu.is_active,
                Role.is_active,
            )
        ).all()
    resolved_permissions = sorted(
        set(
            filter_module_scoped_permissions(
                session=session,
                tenant_id=tenant_context.tenant_id,
                permission_codes=[permission for permission in permissions if permission],
            )
        )
    )
    redis_cache.set_json(cache_key, resolved_permissions)
    return resolved_permissions


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
            raise HTTPException(
                status_code=409, detail="Permission code already exists"
            )

    menu = Menu.model_validate(menu_in)
    session.add(menu)
    session.commit()
    session.refresh(menu)
    redis_cache.bump_namespace(CacheNamespace.RBAC)
    return menu


@router.patch(
    "/{menu_id}",
    dependencies=[Depends(require_permission("system:menu:update"))],
    response_model=MenuPublic,
)
def update_menu(*, session: SessionDep, menu_id: uuid.UUID, menu_in: MenuUpdate) -> Any:
    menu = session.get(Menu, menu_id)
    if not menu:
        raise HTTPException(status_code=404, detail="Menu not found")
    if menu_in.parent_id == menu_id:
        raise HTTPException(status_code=400, detail="Menu cannot be its own parent")
    if menu_in.parent_id and not session.get(Menu, menu_in.parent_id):
        raise HTTPException(status_code=400, detail="Parent menu does not exist")
    if menu_in.parent_id and is_descendant_menu(
        session=session,
        menu_id=menu_id,
        possible_descendant_id=menu_in.parent_id,
    ):
        raise HTTPException(status_code=400, detail="Menu parent cannot be a child")
    if menu_in.permission_code and menu_in.permission_code != menu.permission_code:
        existing_menu = session.exec(
            select(Menu).where(Menu.permission_code == menu_in.permission_code)
        ).first()
        if existing_menu:
            raise HTTPException(
                status_code=409, detail="Permission code already exists"
            )

    menu.sqlmodel_update(menu_in.model_dump(exclude_unset=True))
    menu.updated_at = get_datetime_utc()
    session.add(menu)
    session.commit()
    session.refresh(menu)
    redis_cache.bump_namespace(CacheNamespace.RBAC)
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
    redis_cache.bump_namespace(CacheNamespace.RBAC)
    return Response(status_code=204)
