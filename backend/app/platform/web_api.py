import uuid
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends

from app.api import deps as _deps
from app.core.data_permissions import build_owner_data_scope_filter_for_principal


@dataclass(frozen=True)
class Principal:
    """Stable request identity exposed to business module routes."""

    id: uuid.UUID
    is_superuser: bool


@dataclass(frozen=True)
class TenantContext:
    """Stable tenant selection exposed to business module routes."""

    tenant_id: uuid.UUID
    tenant_code: str
    user_id: uuid.UUID


def get_current_principal(current_user: _deps.CurrentUser) -> Principal:
    return Principal(id=current_user.id, is_superuser=current_user.is_superuser)


def get_current_tenant_context(tenant_context: _deps.CurrentTenant) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_context.tenant_id,
        tenant_code=tenant_context.tenant_code,
        user_id=tenant_context.user_id,
    )


CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]
CurrentTenant = Annotated[TenantContext, Depends(get_current_tenant_context)]
SessionDep = _deps.SessionDep


def build_owner_data_scope_filter(
    *,
    session: SessionDep,
    current_principal: Principal,
    tenant_id: uuid.UUID,
    owner_id_column: Any,
) -> Any:
    return build_owner_data_scope_filter_for_principal(
        session=session,
        principal_id=current_principal.id,
        is_superuser=current_principal.is_superuser,
        tenant_id=tenant_id,
        owner_id_column=owner_id_column,
    )


def normalize_pagination(
    *, page: int, page_size: int, max_page_size: int = 100
) -> tuple[int, int]:
    return _deps.normalize_pagination(
        page=page,
        page_size=page_size,
        max_page_size=max_page_size,
    )


def require_module_access(module_code: str, permission_code: str):
    return _deps.require_module_access(module_code, permission_code)

__all__ = [
    "CurrentTenant",
    "CurrentPrincipal",
    "SessionDep",
    "Principal",
    "TenantContext",
    "build_owner_data_scope_filter",
    "normalize_pagination",
    "require_module_access",
]
