import uuid
from typing import Any

from sqlalchemy import or_, true
from sqlmodel import Session, col, select

from app.models import (
    Department,
    Role,
    RoleDataScopeDepartment,
    TenantMembership,
    User,
    UserRole,
)


def _get_descendant_department_ids(
    *, session: Session, tenant_id: uuid.UUID, root_ids: set[uuid.UUID]
) -> set[uuid.UUID]:
    department_ids = set(root_ids)
    pending = set(root_ids)
    while pending:
        children = set(
            session.exec(
                select(Department.id).where(
                    Department.tenant_id == tenant_id,
                    col(Department.parent_id).in_(pending),
                )
            ).all()
        )
        pending = children - department_ids
        department_ids.update(children)
    return department_ids


def build_owner_data_scope_filter(
    *,
    session: Session,
    current_user: User,
    tenant_id: uuid.UUID,
    owner_id_column: Any,
) -> Any:
    """Build the tenant-local owner predicate granted by the user's active roles."""
    if current_user.is_superuser:
        return true()

    roles = session.exec(
        select(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(
            UserRole.user_id == current_user.id,
            UserRole.tenant_id == tenant_id,
            Role.tenant_id == tenant_id,
            Role.is_active,
        )
    ).all()
    if any(role.data_scope == "all" for role in roles):
        return true()

    membership = session.exec(
        select(TenantMembership).where(
            TenantMembership.user_id == current_user.id,
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.is_active,
        )
    ).first()
    department_ids: set[uuid.UUID] = set()
    if membership and membership.department_id:
        if any(role.data_scope == "department" for role in roles):
            department_ids.add(membership.department_id)
        if any(role.data_scope == "department_and_children" for role in roles):
            department_ids.update(
                _get_descendant_department_ids(
                    session=session,
                    tenant_id=tenant_id,
                    root_ids={membership.department_id},
                )
            )

    custom_role_ids = {role.id for role in roles if role.data_scope == "custom"}
    if custom_role_ids:
        department_ids.update(
            session.exec(
                select(RoleDataScopeDepartment.department_id).where(
                    RoleDataScopeDepartment.tenant_id == tenant_id,
                    col(RoleDataScopeDepartment.role_id).in_(custom_role_ids),
                )
            ).all()
        )

    predicates = [owner_id_column == current_user.id]
    if department_ids:
        scoped_user_ids = select(TenantMembership.user_id).where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.is_active,
            col(TenantMembership.department_id).in_(department_ids),
        )
        predicates.append(col(owner_id_column).in_(scoped_user_ids))
    return or_(*predicates)
