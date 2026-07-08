from typing import Any

from fastapi import APIRouter
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.models import Menu, RoleMenu, UserRole

router = APIRouter(prefix="/permissions", tags=["permissions"])


@router.get("/me", response_model=list[str])
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
