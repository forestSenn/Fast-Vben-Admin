import uuid
from dataclasses import dataclass

from sqlmodel import Session, col, select

from app.models import Tenant, TenantMembership

DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
DEFAULT_TENANT_CODE = "default"


@dataclass(frozen=True)
class TenantContext:
    tenant_id: uuid.UUID
    tenant_code: str
    user_id: uuid.UUID


def get_default_tenant(session: Session) -> Tenant | None:
    return session.exec(
        select(Tenant).where(Tenant.code == DEFAULT_TENANT_CODE)
    ).first()


def add_user_to_default_tenant(*, session: Session, user_id: uuid.UUID) -> None:
    tenant = get_default_tenant(session)
    if tenant is None:
        return
    add_user_to_tenant(
        session=session,
        user_id=user_id,
        tenant_id=tenant.id,
        is_default=True,
    )


def add_user_to_tenant(
    *,
    session: Session,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    is_default: bool = False,
    department_id: uuid.UUID | None = None,
) -> TenantMembership:
    membership = session.exec(
        select(TenantMembership).where(
            TenantMembership.user_id == user_id,
            TenantMembership.tenant_id == tenant_id,
        )
    ).first()
    if membership is None:
        membership = TenantMembership(
            user_id=user_id,
            tenant_id=tenant_id,
            is_default=is_default,
            department_id=department_id,
        )
        session.add(membership)
    else:
        if is_default and not membership.is_default:
            membership.is_default = True
        if department_id is not None:
            membership.department_id = department_id
        session.add(membership)
    return membership


def get_active_tenant_membership(
    *,
    session: Session,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID | None = None,
) -> tuple[TenantMembership, Tenant] | None:
    statement = (
        select(TenantMembership, Tenant)
        .join(Tenant, Tenant.id == TenantMembership.tenant_id)
        .where(
            TenantMembership.user_id == user_id,
            TenantMembership.is_active,
            Tenant.is_active,
        )
    )
    if tenant_id is not None:
        statement = statement.where(TenantMembership.tenant_id == tenant_id)
    else:
        statement = statement.order_by(
            col(TenantMembership.is_default).desc(),
            col(TenantMembership.created_at),
        )
    row = session.exec(statement).first()
    if row is None:
        return None
    return row
