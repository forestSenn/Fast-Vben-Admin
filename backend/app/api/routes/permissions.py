from typing import Any

from fastapi import APIRouter
from sqlmodel import select

from app.api.deps import CurrentTenant, CurrentUser, SessionDep
from app.core.cache import CacheNamespace, redis_cache
from app.models import Menu, Role, RoleMenu, UserRole

router = APIRouter(prefix="/permissions", tags=["permissions"])


@router.get("/me", response_model=list[str])
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
        {permission for permission in permissions if permission}
    )
    redis_cache.set_json(cache_key, resolved_permissions)
    return resolved_permissions
