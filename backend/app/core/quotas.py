import uuid

from fastapi import HTTPException
from sqlmodel import Session, func, select

from app.models import FileAsset, Tenant, TenantMembership, TenantPlan


def get_tenant_plan(*, session: Session, tenant_id: uuid.UUID) -> TenantPlan:
    plan = session.exec(
        select(TenantPlan)
        .join(Tenant, Tenant.plan_id == TenantPlan.id)
        .where(Tenant.id == tenant_id)
    ).first()
    if plan is None:
        raise HTTPException(status_code=409, detail="Tenant plan is not configured")
    return plan


def get_member_count(*, session: Session, tenant_id: uuid.UUID) -> int:
    return session.exec(
        select(func.count())
        .select_from(TenantMembership)
        .where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.is_active,
        )
    ).one()


def get_file_usage(*, session: Session, tenant_id: uuid.UUID) -> tuple[int, int]:
    count, storage_bytes = session.exec(
        select(func.count(), func.coalesce(func.sum(FileAsset.size), 0)).where(
            FileAsset.tenant_id == tenant_id
        )
    ).one()
    return count, storage_bytes


def ensure_member_quota(*, session: Session, tenant_id: uuid.UUID) -> None:
    plan = get_tenant_plan(session=session, tenant_id=tenant_id)
    if plan.max_members is None:
        return
    if get_member_count(session=session, tenant_id=tenant_id) >= plan.max_members:
        raise HTTPException(status_code=409, detail="Tenant member quota exceeded")


def ensure_file_quota(
    *,
    session: Session,
    tenant_id: uuid.UUID,
    incoming_size: int,
) -> None:
    plan = get_tenant_plan(session=session, tenant_id=tenant_id)
    file_assets, storage_bytes = get_file_usage(
        session=session,
        tenant_id=tenant_id,
    )
    if plan.max_file_assets is not None and file_assets >= plan.max_file_assets:
        raise HTTPException(status_code=409, detail="Tenant file quota exceeded")
    if (
        plan.max_storage_bytes is not None
        and storage_bytes + incoming_size > plan.max_storage_bytes
    ):
        raise HTTPException(status_code=409, detail="Tenant storage quota exceeded")
