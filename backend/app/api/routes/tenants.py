import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlmodel import and_, col, delete, func, or_, select

from app.api.deps import (
    CurrentTenant,
    CurrentTokenPayload,
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
    normalize_pagination,
)
from app.api.routes.login import create_login_token
from app.core.cache import CacheNamespace, redis_cache
from app.core.db import (
    ensure_tenant_plan_profile,
    ensure_tenant_profile,
    provision_tenant_roles,
    sync_tenant_plan_role_menus,
)
from app.core.quotas import get_file_usage, get_member_count
from app.core.security import get_password_hash
from app.core.tenancy import DEFAULT_TENANT_ID
from app.models import (
    Menu,
    Tenant,
    TenantCreate,
    TenantInitializationTemplate,
    TenantInitializationTemplateCreate,
    TenantInitializationTemplatePublic,
    TenantInitializationTemplatesPublic,
    TenantInitializationTemplateUpdate,
    TenantLifecycleAction,
    TenantLifecycleActionRequest,
    TenantLifecycleStatus,
    TenantMembership,
    TenantMembershipPublic,
    TenantMenuSyncResult,
    TenantPlan,
    TenantPlanCreate,
    TenantPlanMenu,
    TenantPlanMenuUpdate,
    TenantPlanProfile,
    TenantPlanPublic,
    TenantPlansPublic,
    TenantPlanUpdate,
    TenantProfile,
    TenantPublic,
    TenantsPublic,
    TenantSwitchRequest,
    TenantUpdate,
    TenantUsagePublic,
    Token,
    User,
    UserSession,
    get_datetime_utc,
)
from app.modules.outbox import enqueue_event

router = APIRouter(prefix="/tenants", tags=["tenants"])
logger = logging.getLogger(__name__)


def ensure_tenant_is_mutable(tenant_id: uuid.UUID) -> None:
    if tenant_id == DEFAULT_TENANT_ID:
        raise HTTPException(
            status_code=400,
            detail="Default tenant cannot be modified",
        )


def ensure_tenant_plan_is_mutable(plan: TenantPlan) -> None:
    if plan.is_default:
        raise HTTPException(
            status_code=400,
            detail="Default tenant plan cannot be modified",
        )


TENANT_FIELDS = {"code", "name", "description", "is_active"}
TENANT_PROFILE_FIELDS = {
    "contact_name",
    "contact_mobile",
    "industry",
    "address_code",
    "address_detail",
    "qualifications",
    "website",
    "account_count",
    "lifecycle_status",
    "effective_at",
    "trial_ends_at",
    "service_expires_at",
    "frozen_reason",
    "owner_name",
    "customer_source",
    "follow_up_notes",
}
PLAN_FIELDS = {
    "code",
    "name",
    "description",
    "max_members",
    "max_file_assets",
    "max_storage_bytes",
    "is_default",
    "is_active",
}
PLAN_PROFILE_FIELD_MAP = {
    "type": "package_type",
    "logo": "logo",
    "price": "price",
    "published": "published",
    "order_num": "order_num",
    "remark": "remark",
}


def normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def effective_lifecycle_status(
    profile: TenantProfile, *, now: datetime | None = None
) -> TenantLifecycleStatus:
    current_time = now or get_datetime_utc()
    if profile.lifecycle_status in {
        TenantLifecycleStatus.FROZEN,
        TenantLifecycleStatus.ARCHIVED,
    }:
        return profile.lifecycle_status
    service_expires_at = normalize_datetime(profile.service_expires_at)
    trial_ends_at = normalize_datetime(profile.trial_ends_at)
    if service_expires_at is not None and service_expires_at <= current_time:
        return TenantLifecycleStatus.EXPIRED
    if (
        profile.lifecycle_status == TenantLifecycleStatus.TRIAL
        and trial_ends_at is not None
        and trial_ends_at <= current_time
    ):
        return TenantLifecycleStatus.EXPIRED
    return profile.lifecycle_status


def validate_tenant_periods(profile: TenantProfile) -> None:
    effective_at = normalize_datetime(profile.effective_at)
    trial_ends_at = normalize_datetime(profile.trial_ends_at)
    service_expires_at = normalize_datetime(profile.service_expires_at)
    if effective_at and trial_ends_at and trial_ends_at <= effective_at:
        raise HTTPException(
            status_code=400, detail="Trial end time must be after effective time"
        )
    if effective_at and service_expires_at and service_expires_at <= effective_at:
        raise HTTPException(
            status_code=400, detail="Service expiry time must be after effective time"
        )
    if profile.lifecycle_status == TenantLifecycleStatus.TRIAL and not trial_ends_at:
        raise HTTPException(status_code=400, detail="Trial tenant requires trial end time")


def apply_tenant_profile_input(
    *, profile: TenantProfile, data: dict[str, Any]
) -> None:
    profile_data = {
        key: value for key, value in data.items() if key in TENANT_PROFILE_FIELDS
    }
    if "type" in data:
        profile_data["tenant_type"] = data["type"]
    for field_name in ("effective_at", "trial_ends_at", "service_expires_at"):
        if field_name in profile_data:
            profile_data[field_name] = normalize_datetime(profile_data[field_name])
    profile.sqlmodel_update(profile_data)
    profile.updated_at = get_datetime_utc()
    validate_tenant_periods(profile)


def build_tenant_plan_public(
    *, session: SessionDep, plan: TenantPlan
) -> TenantPlanPublic:
    profile = session.get(TenantPlanProfile, plan.id)
    menu_count = session.exec(
        select(func.count())
        .select_from(TenantPlanMenu)
        .where(TenantPlanMenu.plan_id == plan.id)
    ).one()
    profile_data: dict[str, Any] = {}
    if profile is not None:
        profile_data = {
            "type": profile.package_type,
            "logo": profile.logo,
            "price": profile.price,
            "published": profile.published,
            "order_num": profile.order_num,
            "subscription_num": profile.subscription_num,
            "subscription_total_amount": profile.subscription_total_amount,
            "remark": profile.remark,
        }
    return TenantPlanPublic.model_validate(
        plan,
        update={**profile_data, "menu_count": menu_count},
    )


def apply_plan_profile_input(
    *, profile: TenantPlanProfile, data: dict[str, Any]
) -> None:
    profile.sqlmodel_update(
        {
            profile_field: data[input_field]
            for input_field, profile_field in PLAN_PROFILE_FIELD_MAP.items()
            if input_field in data
        }
    )
    profile.updated_at = get_datetime_utc()


def build_lifecycle_filter(
    lifecycle_status: TenantLifecycleStatus, *, now: datetime
) -> Any:
    expired = or_(
        TenantProfile.lifecycle_status == TenantLifecycleStatus.EXPIRED,
        TenantProfile.service_expires_at <= now,
        and_(
            TenantProfile.lifecycle_status == TenantLifecycleStatus.TRIAL,
            TenantProfile.trial_ends_at <= now,
        ),
    )
    if lifecycle_status == TenantLifecycleStatus.EXPIRED:
        return expired
    if lifecycle_status in {
        TenantLifecycleStatus.TRIAL,
        TenantLifecycleStatus.FORMAL,
    }:
        conditions = [
            TenantProfile.lifecycle_status == lifecycle_status,
            or_(
                TenantProfile.service_expires_at.is_(None),
                TenantProfile.service_expires_at > now,
            ),
        ]
        if lifecycle_status == TenantLifecycleStatus.TRIAL:
            conditions.append(
                or_(
                TenantProfile.trial_ends_at.is_(None),
                TenantProfile.trial_ends_at > now,
                )
            )
        return and_(*conditions)
    return TenantProfile.lifecycle_status == lifecycle_status


def get_tenant_or_404(*, session: SessionDep, tenant_id: uuid.UUID) -> Tenant:
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


def get_plan_or_404(*, session: SessionDep, plan_id: uuid.UUID) -> TenantPlan:
    plan = session.get(TenantPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Tenant plan not found")
    return plan


def get_default_plan(*, session: SessionDep) -> TenantPlan:
    plan = session.exec(
        select(TenantPlan).where(TenantPlan.is_default, TenantPlan.is_active)
    ).first()
    if plan is None:
        raise HTTPException(
            status_code=409, detail="Default tenant plan is not configured"
        )
    return plan


def resolve_active_plan(
    *, session: SessionDep, plan_id: uuid.UUID | None
) -> TenantPlan:
    plan = (
        get_plan_or_404(session=session, plan_id=plan_id)
        if plan_id is not None
        else get_default_plan(session=session)
    )
    if not plan.is_active:
        raise HTTPException(status_code=400, detail="Tenant plan is disabled")
    return plan


def get_template_or_404(
    *, session: SessionDep, template_id: uuid.UUID
) -> TenantInitializationTemplate:
    template = session.get(TenantInitializationTemplate, template_id)
    if template is None:
        raise HTTPException(
            status_code=404, detail="Tenant initialization template not found"
        )
    return template


def get_default_template(*, session: SessionDep) -> TenantInitializationTemplate:
    template = session.exec(
        select(TenantInitializationTemplate).where(
            TenantInitializationTemplate.is_default,
            TenantInitializationTemplate.is_active,
        )
    ).first()
    if template is None:
        raise HTTPException(
            status_code=409,
            detail="Default tenant initialization template is not configured",
        )
    return template


def resolve_active_template(
    *, session: SessionDep, template_id: uuid.UUID | None
) -> TenantInitializationTemplate:
    template = (
        get_template_or_404(session=session, template_id=template_id)
        if template_id is not None
        else get_default_template(session=session)
    )
    if not template.is_active:
        raise HTTPException(
            status_code=400, detail="Tenant initialization template is disabled"
        )
    return template


def build_tenant_public(*, session: SessionDep, tenant: Tenant) -> TenantPublic:
    plan = session.get(TenantPlan, tenant.plan_id)
    template = session.get(
        TenantInitializationTemplate, tenant.initialization_template_id
    )
    profile = session.get(TenantProfile, tenant.id)
    profile_data: dict[str, Any] = {}
    effective_status = TenantLifecycleStatus.FORMAL
    if profile is not None:
        effective_status = effective_lifecycle_status(profile)
        profile_data = {
            "contact_user_id": profile.contact_user_id,
            "contact_name": profile.contact_name,
            "contact_mobile": profile.contact_mobile,
            "industry": profile.industry,
            "type": profile.tenant_type,
            "address_code": profile.address_code,
            "address_detail": profile.address_detail,
            "qualifications": profile.qualifications,
            "website": profile.website,
            "recharge_amount": profile.recharge_amount,
            "payment_amount": profile.payment_amount,
            "balance_amount": profile.balance_amount,
            "account_count": profile.account_count,
            "lifecycle_status": effective_status,
            "effective_at": profile.effective_at,
            "trial_ends_at": profile.trial_ends_at,
            "service_expires_at": profile.service_expires_at,
            "frozen_at": profile.frozen_at,
            "frozen_reason": profile.frozen_reason,
            "owner_name": profile.owner_name,
            "customer_source": profile.customer_source,
            "follow_up_notes": profile.follow_up_notes,
        }
    return TenantPublic.model_validate(
        tenant,
        update={
            **profile_data,
            "is_active": tenant.is_active
            and effective_status
            in {TenantLifecycleStatus.TRIAL, TenantLifecycleStatus.FORMAL},
            "plan_name": plan.name if plan is not None else None,
            "initialization_template_name": (
                template.name if template is not None else None
            ),
            "current_account_count": get_member_count(
                session=session, tenant_id=tenant.id
            ),
        },
    )


def set_default_plan(*, session: SessionDep, plan: TenantPlan) -> None:
    for current_default in session.exec(
        select(TenantPlan).where(TenantPlan.is_default, TenantPlan.id != plan.id)
    ).all():
        current_default.is_default = False
        current_default.updated_at = get_datetime_utc()
        session.add(current_default)
    plan.is_default = True
    plan.is_active = True


def set_default_template(
    *, session: SessionDep, template: TenantInitializationTemplate
) -> None:
    for current_default in session.exec(
        select(TenantInitializationTemplate).where(
            TenantInitializationTemplate.is_default,
            TenantInitializationTemplate.id != template.id,
        )
    ).all():
        current_default.is_default = False
        current_default.updated_at = get_datetime_utc()
        session.add(current_default)
    template.is_default = True
    template.is_active = True


def revoke_tenant_sessions(*, session: SessionDep, tenant_id: uuid.UUID) -> None:
    revoked_at = get_datetime_utc()
    sessions = session.exec(
        select(UserSession).where(
            UserSession.tenant_id == tenant_id,
            UserSession.revoked_at.is_(None),
        )
    ).all()
    for user_session in sessions:
        user_session.revoked_at = revoked_at
        session.add(user_session)


def resolve_plan_menu_ids(
    *, session: SessionDep, menu_ids: list[uuid.UUID]
) -> set[uuid.UUID]:
    requested_ids = set(menu_ids)
    if not requested_ids:
        return set()
    menus = session.exec(select(Menu).where(col(Menu.id).in_(requested_ids))).all()
    if len(menus) != len(requested_ids):
        raise HTTPException(status_code=400, detail="Some menus do not exist")
    if any((menu.permission_code or "").startswith("platform:") for menu in menus):
        raise HTTPException(
            status_code=400,
            detail="Platform management menus cannot be granted to tenant plans",
        )

    resolved_ids = set(requested_ids)
    pending_parent_ids = {
        menu.parent_id for menu in menus if menu.parent_id is not None
    }
    while pending_parent_ids:
        parents = session.exec(
            select(Menu).where(col(Menu.id).in_(pending_parent_ids))
        ).all()
        pending_parent_ids = set()
        for parent in parents:
            if (parent.permission_code or "").startswith("platform:"):
                raise HTTPException(
                    status_code=400,
                    detail="Tenant plan menu cannot inherit from a platform menu",
                )
            if parent.id in resolved_ids:
                continue
            resolved_ids.add(parent.id)
            if parent.parent_id is not None:
                pending_parent_ids.add(parent.parent_id)
    return resolved_ids


def sync_plan_tenants(
    *, session: SessionDep, plan_id: uuid.UUID
) -> TenantMenuSyncResult:
    result = TenantMenuSyncResult()
    tenants = session.exec(select(Tenant).where(Tenant.plan_id == plan_id)).all()
    for tenant in tenants:
        try:
            with session.begin_nested():
                synced = sync_tenant_plan_role_menus(session=session, tenant=tenant)
                session.flush()
        except Exception:
            logger.exception("Failed to sync tenant menus for tenant %s", tenant.id)
            result.failed_count += 1
        else:
            if synced:
                result.success_count += 1
            else:
                result.skipped_count += 1
    return result


@router.get("/me", response_model=list[TenantMembershipPublic])
def read_my_tenants(
    session: SessionDep,
    current_user: CurrentUser,
    tenant_context: CurrentTenant,
) -> Any:
    rows = session.exec(
        select(TenantMembership, Tenant)
        .join(Tenant, Tenant.id == TenantMembership.tenant_id)
        .where(TenantMembership.user_id == current_user.id)
        .order_by(col(TenantMembership.is_default).desc(), col(Tenant.name))
    ).all()
    return [
        TenantMembershipPublic(
            tenant=build_tenant_public(session=session, tenant=tenant),
            is_active=membership.is_active,
            is_default=membership.is_default,
            is_current=tenant.id == tenant_context.tenant_id,
            created_at=membership.created_at,
        )
        for membership, tenant in rows
    ]


@router.post("/switch", response_model=Token)
def switch_tenant(
    *,
    session: SessionDep,
    request: Request,
    current_user: CurrentUser,
    token_data: CurrentTokenPayload,
    body: TenantSwitchRequest,
) -> Token:
    token = create_login_token(
        session=session,
        request=request,
        user=current_user,
        tenant_id=body.tenant_id,
    )
    if token_data.jti:
        old_session = session.exec(
            select(UserSession).where(
                UserSession.user_id == current_user.id,
                UserSession.token_jti == token_data.jti,
            )
        ).first()
        if old_session is not None:
            old_session.revoked_at = get_datetime_utc()
            session.add(old_session)
            session.commit()
    return token


@router.get(
    "",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=TenantsPublic,
)
def read_tenants(
    session: SessionDep,
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    is_active: bool | None = None,
    lifecycle_status: TenantLifecycleStatus | None = None,
    plan_id: uuid.UUID | None = None,
    initialization_template_id: uuid.UUID | None = None,
    industry: int | None = None,
    owner_name: str | None = None,
    customer_source: str | None = None,
    expires_before: datetime | None = None,
    expiring_in_days: int | None = None,
) -> Any:
    page, page_size = normalize_pagination(page=page, page_size=page_size)
    now = get_datetime_utc()
    filters = []
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            or_(
                col(Tenant.code).ilike(pattern),
                col(Tenant.name).ilike(pattern),
                col(TenantProfile.contact_name).ilike(pattern),
                col(TenantProfile.contact_mobile).ilike(pattern),
            )
        )
    if is_active is not None:
        filters.append(Tenant.is_active == is_active)
    if lifecycle_status is not None:
        filters.append(build_lifecycle_filter(lifecycle_status, now=now))
    if plan_id is not None:
        filters.append(Tenant.plan_id == plan_id)
    if initialization_template_id is not None:
        filters.append(
            Tenant.initialization_template_id == initialization_template_id
        )
    if industry is not None:
        filters.append(TenantProfile.industry == industry)
    if owner_name:
        filters.append(col(TenantProfile.owner_name).ilike(f"%{owner_name}%"))
    if customer_source:
        filters.append(
            col(TenantProfile.customer_source).ilike(f"%{customer_source}%")
        )
    normalized_expires_before = normalize_datetime(expires_before)
    if expiring_in_days is not None:
        if expiring_in_days < 1 or expiring_in_days > 3650:
            raise HTTPException(
                status_code=422,
                detail="expiring_in_days must be between 1 and 3650",
            )
        normalized_expires_before = now + timedelta(days=expiring_in_days)
        filters.extend(
            [
                TenantProfile.service_expires_at > now,
                TenantProfile.service_expires_at <= normalized_expires_before,
            ]
        )
    elif normalized_expires_before is not None:
        filters.append(
            TenantProfile.service_expires_at <= normalized_expires_before
        )
    count = session.exec(
        select(func.count())
        .select_from(Tenant)
        .outerjoin(TenantProfile, TenantProfile.tenant_id == Tenant.id)
        .where(*filters)
    ).one()
    tenants = session.exec(
        select(Tenant)
        .outerjoin(TenantProfile, TenantProfile.tenant_id == Tenant.id)
        .where(*filters)
        .order_by(col(Tenant.created_at).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return TenantsPublic(
        items=[
            build_tenant_public(session=session, tenant=tenant) for tenant in tenants
        ],
        total=count,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/plans",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=TenantPlansPublic,
)
def read_tenant_plans(
    session: SessionDep,
    page: int = 1,
    page_size: int = 50,
    keyword: str | None = None,
    is_active: bool | None = None,
    type: int | None = None,
    published: int | None = None,
) -> Any:
    page, page_size = normalize_pagination(page=page, page_size=page_size)
    filters = []
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            or_(
                col(TenantPlan.code).ilike(pattern), col(TenantPlan.name).ilike(pattern)
            )
        )
    if is_active is not None:
        filters.append(TenantPlan.is_active == is_active)
    if type is not None:
        filters.append(TenantPlanProfile.package_type == type)
    if published is not None:
        filters.append(TenantPlanProfile.published == published)
    count = session.exec(
        select(func.count())
        .select_from(TenantPlan)
        .outerjoin(TenantPlanProfile, TenantPlanProfile.plan_id == TenantPlan.id)
        .where(*filters)
    ).one()
    plans = session.exec(
        select(TenantPlan)
        .outerjoin(TenantPlanProfile, TenantPlanProfile.plan_id == TenantPlan.id)
        .where(*filters)
        .order_by(col(TenantPlan.is_default).desc(), col(TenantPlan.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return TenantPlansPublic(
        items=[build_tenant_plan_public(session=session, plan=plan) for plan in plans],
        total=count,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/plans/simple",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=list[TenantPlanPublic],
)
def read_simple_tenant_plans(session: SessionDep) -> Any:
    plans = session.exec(
        select(TenantPlan)
        .where(TenantPlan.is_active)
        .order_by(col(TenantPlan.is_default).desc(), col(TenantPlan.name))
    ).all()
    return [build_tenant_plan_public(session=session, plan=plan) for plan in plans]


@router.get(
    "/plans/{plan_id}/menus",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=list[uuid.UUID],
)
def read_tenant_plan_menus(
    *, session: SessionDep, plan_id: uuid.UUID
) -> list[uuid.UUID]:
    get_plan_or_404(session=session, plan_id=plan_id)
    return list(
        session.exec(
            select(TenantPlanMenu.menu_id).where(TenantPlanMenu.plan_id == plan_id)
        ).all()
    )


@router.put(
    "/plans/{plan_id}/menus",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=list[uuid.UUID],
)
def update_tenant_plan_menus(
    *,
    session: SessionDep,
    plan_id: uuid.UUID,
    body: TenantPlanMenuUpdate,
) -> list[uuid.UUID]:
    plan = get_plan_or_404(session=session, plan_id=plan_id)
    ensure_tenant_plan_is_mutable(plan)
    resolved_ids = resolve_plan_menu_ids(session=session, menu_ids=body.menu_ids)
    session.exec(delete(TenantPlanMenu).where(TenantPlanMenu.plan_id == plan.id))
    for menu_id in resolved_ids:
        session.add(TenantPlanMenu(plan_id=plan.id, menu_id=menu_id))
    plan.updated_at = get_datetime_utc()
    session.add(plan)
    session.commit()
    return list(resolved_ids)


@router.post(
    "/plans/{plan_id}/sync-menus",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=TenantMenuSyncResult,
)
def sync_tenant_plan_menus(
    *, session: SessionDep, plan_id: uuid.UUID
) -> TenantMenuSyncResult:
    get_plan_or_404(session=session, plan_id=plan_id)
    result = sync_plan_tenants(session=session, plan_id=plan_id)
    session.commit()
    redis_cache.bump_namespace(CacheNamespace.RBAC)
    return result


@router.post(
    "/plans",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=TenantPlanPublic,
)
def create_tenant_plan(
    *, session: SessionDep, plan_in: TenantPlanCreate
) -> TenantPlanPublic:
    if session.exec(select(TenantPlan).where(TenantPlan.code == plan_in.code)).first():
        raise HTTPException(status_code=409, detail="Tenant plan code already exists")
    input_data = plan_in.model_dump()
    current_default = session.exec(
        select(TenantPlan).where(TenantPlan.is_default)
    ).first()
    plan = TenantPlan.model_validate(
        {key: value for key, value in input_data.items() if key in PLAN_FIELDS}
    )
    if plan.is_default:
        set_default_plan(session=session, plan=plan)
    session.add(plan)
    session.flush()
    profile = ensure_tenant_plan_profile(session=session, plan=plan)
    apply_plan_profile_input(profile=profile, data=input_data)
    session.add(profile)
    source_plan = current_default if current_default and current_default.id != plan.id else None
    if source_plan is not None:
        source_menu_ids = session.exec(
            select(TenantPlanMenu.menu_id).where(
                TenantPlanMenu.plan_id == source_plan.id
            )
        ).all()
    else:
        source_menu_ids = session.exec(
            select(Menu.id).where(
                or_(
                    Menu.permission_code.is_(None),
                    ~col(Menu.permission_code).startswith("platform:"),
                )
            )
        ).all()
    for menu_id in set(source_menu_ids):
        session.add(TenantPlanMenu(plan_id=plan.id, menu_id=menu_id))
    session.commit()
    session.refresh(plan)
    return build_tenant_plan_public(session=session, plan=plan)


@router.patch(
    "/plans/{plan_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=TenantPlanPublic,
)
def update_tenant_plan(
    *,
    session: SessionDep,
    plan_id: uuid.UUID,
    plan_in: TenantPlanUpdate,
) -> TenantPlanPublic:
    plan = get_plan_or_404(session=session, plan_id=plan_id)
    ensure_tenant_plan_is_mutable(plan)
    input_data = plan_in.model_dump(exclude_unset=True)
    update_data = {
        key: value for key, value in input_data.items() if key in PLAN_FIELDS
    }
    new_code = update_data.get("code")
    if new_code and new_code != plan.code:
        existing = session.exec(
            select(TenantPlan).where(TenantPlan.code == new_code)
        ).first()
        if existing is not None:
            raise HTTPException(
                status_code=409, detail="Tenant plan code already exists"
            )
    if update_data.get("is_active") is False:
        bound_tenant = session.exec(
            select(Tenant).where(Tenant.plan_id == plan.id)
        ).first()
        if bound_tenant is not None:
            raise HTTPException(status_code=400, detail="Tenant plan is in use")
    plan.sqlmodel_update(update_data)
    if update_data.get("is_default"):
        set_default_plan(session=session, plan=plan)
    plan.updated_at = get_datetime_utc()
    session.add(plan)
    profile = ensure_tenant_plan_profile(session=session, plan=plan)
    apply_plan_profile_input(profile=profile, data=input_data)
    session.add(profile)
    session.commit()
    session.refresh(plan)
    return build_tenant_plan_public(session=session, plan=plan)


@router.delete(
    "/plans/{plan_id}",
    dependencies=[Depends(get_current_active_superuser)],
    status_code=204,
)
def delete_tenant_plan(*, session: SessionDep, plan_id: uuid.UUID) -> Response:
    plan = get_plan_or_404(session=session, plan_id=plan_id)
    ensure_tenant_plan_is_mutable(plan)
    if session.exec(select(Tenant).where(Tenant.plan_id == plan.id)).first():
        raise HTTPException(status_code=400, detail="Tenant plan is in use")
    session.delete(plan)
    session.commit()
    return Response(status_code=204)


@router.get(
    "/templates",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=TenantInitializationTemplatesPublic,
)
def read_tenant_templates(
    session: SessionDep,
    page: int = 1,
    page_size: int = 50,
    keyword: str | None = None,
    is_active: bool | None = None,
) -> TenantInitializationTemplatesPublic:
    page, page_size = normalize_pagination(page=page, page_size=page_size)
    filters = []
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            or_(
                col(TenantInitializationTemplate.code).ilike(pattern),
                col(TenantInitializationTemplate.name).ilike(pattern),
            )
        )
    if is_active is not None:
        filters.append(TenantInitializationTemplate.is_active == is_active)
    count = session.exec(
        select(func.count()).select_from(TenantInitializationTemplate).where(*filters)
    ).one()
    templates = session.exec(
        select(TenantInitializationTemplate)
        .where(*filters)
        .order_by(
            col(TenantInitializationTemplate.is_default).desc(),
            col(TenantInitializationTemplate.created_at),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return TenantInitializationTemplatesPublic(
        items=[
            TenantInitializationTemplatePublic.model_validate(template)
            for template in templates
        ],
        total=count,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/templates/simple",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=list[TenantInitializationTemplatePublic],
)
def read_simple_tenant_templates(
    session: SessionDep,
) -> list[TenantInitializationTemplatePublic]:
    templates = session.exec(
        select(TenantInitializationTemplate)
        .where(TenantInitializationTemplate.is_active)
        .order_by(
            col(TenantInitializationTemplate.is_default).desc(),
            col(TenantInitializationTemplate.name),
        )
    ).all()
    return [
        TenantInitializationTemplatePublic.model_validate(template)
        for template in templates
    ]


@router.post(
    "/templates",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=TenantInitializationTemplatePublic,
)
def create_tenant_template(
    *, session: SessionDep, template_in: TenantInitializationTemplateCreate
) -> TenantInitializationTemplatePublic:
    if session.exec(
        select(TenantInitializationTemplate).where(
            TenantInitializationTemplate.code == template_in.code
        )
    ).first():
        raise HTTPException(
            status_code=409, detail="Tenant initialization template code already exists"
        )
    template = TenantInitializationTemplate.model_validate(template_in)
    if template.is_default:
        set_default_template(session=session, template=template)
    session.add(template)
    session.commit()
    session.refresh(template)
    return TenantInitializationTemplatePublic.model_validate(template)


@router.patch(
    "/templates/{template_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=TenantInitializationTemplatePublic,
)
def update_tenant_template(
    *,
    session: SessionDep,
    template_id: uuid.UUID,
    template_in: TenantInitializationTemplateUpdate,
) -> TenantInitializationTemplatePublic:
    template = get_template_or_404(session=session, template_id=template_id)
    update_data = template_in.model_dump(exclude_unset=True)
    new_code = update_data.get("code")
    if new_code and new_code != template.code:
        existing = session.exec(
            select(TenantInitializationTemplate).where(
                TenantInitializationTemplate.code == new_code
            )
        ).first()
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail="Tenant initialization template code already exists",
            )
    if template.is_default and update_data.get("is_default") is False:
        raise HTTPException(status_code=400, detail="Default template cannot be unset")
    if template.is_default and update_data.get("is_active") is False:
        raise HTTPException(
            status_code=400, detail="Default template cannot be disabled"
        )
    template.sqlmodel_update(update_data)
    if update_data.get("is_default"):
        set_default_template(session=session, template=template)
    template.updated_at = get_datetime_utc()
    session.add(template)
    session.commit()
    session.refresh(template)
    return TenantInitializationTemplatePublic.model_validate(template)


@router.delete(
    "/templates/{template_id}",
    dependencies=[Depends(get_current_active_superuser)],
    status_code=204,
)
def delete_tenant_template(*, session: SessionDep, template_id: uuid.UUID) -> Response:
    template = get_template_or_404(session=session, template_id=template_id)
    if template.is_default:
        raise HTTPException(
            status_code=400, detail="Default template cannot be deleted"
        )
    if session.exec(
        select(Tenant).where(Tenant.initialization_template_id == template.id)
    ).first():
        raise HTTPException(status_code=400, detail="Template is in use")
    session.delete(template)
    session.commit()
    return Response(status_code=204)


@router.post(
    "",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=TenantPublic,
)
def create_tenant(
    *, session: SessionDep, current_user: CurrentUser, tenant_in: TenantCreate
) -> Any:
    existing = session.exec(select(Tenant).where(Tenant.code == tenant_in.code)).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Tenant code already exists")
    if bool(tenant_in.username) != bool(tenant_in.password):
        raise HTTPException(
            status_code=400,
            detail="Administrator email and password must be provided together",
        )
    if tenant_in.lifecycle_status not in {
        TenantLifecycleStatus.TRIAL,
        TenantLifecycleStatus.FORMAL,
    }:
        raise HTTPException(
            status_code=400,
            detail="New tenant lifecycle status must be trial or formal",
        )
    if tenant_in.username and session.exec(
        select(User).where(User.email == tenant_in.username)
    ).first():
        raise HTTPException(
            status_code=409, detail="Tenant administrator email already exists"
        )
    plan = resolve_active_plan(session=session, plan_id=tenant_in.plan_id)
    template = resolve_active_template(
        session=session,
        template_id=tenant_in.initialization_template_id,
    )
    input_data = tenant_in.model_dump()
    tenant = Tenant.model_validate(
        {key: value for key, value in input_data.items() if key in TENANT_FIELDS},
        update={
            "plan_id": plan.id,
            "initialization_template_id": template.id,
            "is_active": True,
        },
    )
    session.add(tenant)
    session.flush()
    profile = ensure_tenant_profile(session=session, tenant=tenant)
    apply_tenant_profile_input(profile=profile, data=input_data)
    session.add(profile)

    administrator: User | None = None
    if tenant_in.username and tenant_in.password:
        administrator = User(
            email=tenant_in.username,
            full_name=tenant_in.contact_name or f"{tenant.name}管理员",
            hashed_password=get_password_hash(tenant_in.password),
            is_active=True,
            is_superuser=False,
        )
        session.add(administrator)
        session.flush()
        profile.contact_user_id = administrator.id
        session.add(profile)
    provision_tenant_roles(
        session=session,
        tenant=tenant,
        template=template,
        owner=current_user,
        additional_owners=[administrator] if administrator else None,
    )
    session.commit()
    session.refresh(tenant)
    return build_tenant_public(session=session, tenant=tenant)


@router.get(
    "/{tenant_id}/usage",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=TenantUsagePublic,
)
def read_tenant_usage(
    *, session: SessionDep, tenant_id: uuid.UUID
) -> TenantUsagePublic:
    tenant = get_tenant_or_404(session=session, tenant_id=tenant_id)
    plan = get_plan_or_404(session=session, plan_id=tenant.plan_id)
    file_assets, storage_bytes = get_file_usage(
        session=session,
        tenant_id=tenant.id,
    )
    return TenantUsagePublic(
        tenant_id=tenant.id,
        plan=build_tenant_plan_public(session=session, plan=plan),
        members=get_member_count(session=session, tenant_id=tenant.id),
        file_assets=file_assets,
        storage_bytes=storage_bytes,
    )


@router.post(
    "/{tenant_id}/lifecycle",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=TenantPublic,
)
def operate_tenant_lifecycle(
    *,
    session: SessionDep,
    tenant_id: uuid.UUID,
    body: TenantLifecycleActionRequest,
) -> TenantPublic:
    ensure_tenant_is_mutable(tenant_id)
    tenant = get_tenant_or_404(session=session, tenant_id=tenant_id)
    profile = ensure_tenant_profile(session=session, tenant=tenant)
    now = get_datetime_utc()
    current_status = effective_lifecycle_status(profile, now=now)

    if body.action == TenantLifecycleAction.CONVERT_TO_FORMAL:
        if current_status != TenantLifecycleStatus.TRIAL:
            raise HTTPException(
                status_code=400, detail="Only a trial tenant can become formal"
            )
        profile.lifecycle_status = TenantLifecycleStatus.FORMAL
        profile.effective_at = profile.effective_at or now
    elif body.action == TenantLifecycleAction.RENEW:
        expires_at = normalize_datetime(body.service_expires_at)
        if expires_at is None or expires_at <= now:
            raise HTTPException(
                status_code=400, detail="Renewal expiry time must be in the future"
            )
        profile.service_expires_at = expires_at
        if current_status == TenantLifecycleStatus.EXPIRED:
            profile.lifecycle_status = TenantLifecycleStatus.FORMAL
        elif current_status == TenantLifecycleStatus.FROZEN:
            status_before_freeze = profile.lifecycle_status_before_freeze
            trial_ends_at = normalize_datetime(profile.trial_ends_at)
            if status_before_freeze == TenantLifecycleStatus.EXPIRED or (
                status_before_freeze == TenantLifecycleStatus.TRIAL
                and trial_ends_at is not None
                and trial_ends_at <= now
            ):
                profile.lifecycle_status_before_freeze = TenantLifecycleStatus.FORMAL
        elif current_status == TenantLifecycleStatus.ARCHIVED:
            raise HTTPException(
                status_code=400, detail="Archived tenant cannot be renewed"
            )
    elif body.action == TenantLifecycleAction.FREEZE:
        reason = (body.frozen_reason or "").strip()
        if not reason:
            raise HTTPException(status_code=400, detail="Freeze reason is required")
        if current_status in {
            TenantLifecycleStatus.FROZEN,
            TenantLifecycleStatus.ARCHIVED,
        }:
            raise HTTPException(
                status_code=400, detail="Tenant cannot be frozen in current status"
            )
        profile.lifecycle_status_before_freeze = current_status
        profile.lifecycle_status = TenantLifecycleStatus.FROZEN
        profile.frozen_at = now
        profile.frozen_reason = reason
    elif body.action == TenantLifecycleAction.UNFREEZE:
        if current_status != TenantLifecycleStatus.FROZEN:
            raise HTTPException(status_code=400, detail="Tenant is not frozen")
        restored_status = (
            profile.lifecycle_status_before_freeze or TenantLifecycleStatus.FORMAL
        )
        service_expires_at = normalize_datetime(profile.service_expires_at)
        trial_ends_at = normalize_datetime(profile.trial_ends_at)
        if (
            service_expires_at is not None
            and service_expires_at <= now
            or restored_status == TenantLifecycleStatus.TRIAL
            and trial_ends_at is not None
            and trial_ends_at <= now
        ):
            raise HTTPException(
                status_code=400, detail="Expired tenant must be renewed before unfreeze"
            )
        profile.lifecycle_status = restored_status
        profile.lifecycle_status_before_freeze = None
        profile.frozen_at = None
        profile.frozen_reason = None
    elif body.action == TenantLifecycleAction.ARCHIVE:
        profile.lifecycle_status = TenantLifecycleStatus.ARCHIVED
        profile.lifecycle_status_before_freeze = None

    profile.updated_at = now
    final_status = effective_lifecycle_status(profile, now=now)
    was_active = tenant.is_active
    tenant.is_active = final_status in {
        TenantLifecycleStatus.TRIAL,
        TenantLifecycleStatus.FORMAL,
    }
    tenant.updated_at = now
    session.add(profile)
    session.add(tenant)
    if was_active and not tenant.is_active:
        revoke_tenant_sessions(session=session, tenant_id=tenant.id)
    if body.action == TenantLifecycleAction.ARCHIVE:
        enqueue_event(
            session=session,
            module_code="platform",
            event_type="platform.tenant.archived",
            tenant_id=tenant.id,
            aggregate_id=str(tenant.id),
            payload={"tenant_id": str(tenant.id), "tenant_code": tenant.code},
        )
    session.commit()
    session.refresh(tenant)
    return build_tenant_public(session=session, tenant=tenant)


@router.post(
    "/{tenant_id}/sync-menus",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=TenantMenuSyncResult,
)
def sync_tenant_menus(
    *, session: SessionDep, tenant_id: uuid.UUID
) -> TenantMenuSyncResult:
    ensure_tenant_is_mutable(tenant_id)
    tenant = get_tenant_or_404(session=session, tenant_id=tenant_id)
    synced = sync_tenant_plan_role_menus(session=session, tenant=tenant)
    session.commit()
    redis_cache.bump_namespace(CacheNamespace.RBAC)
    return TenantMenuSyncResult(
        success_count=1 if synced else 0,
        skipped_count=0 if synced else 1,
    )


@router.get(
    "/{tenant_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=TenantPublic,
)
def read_tenant(*, session: SessionDep, tenant_id: uuid.UUID) -> Any:
    tenant = get_tenant_or_404(session=session, tenant_id=tenant_id)
    return build_tenant_public(session=session, tenant=tenant)


@router.patch(
    "/{tenant_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=TenantPublic,
)
def update_tenant(
    *, session: SessionDep, tenant_id: uuid.UUID, tenant_in: TenantUpdate
) -> Any:
    ensure_tenant_is_mutable(tenant_id)
    tenant = get_tenant_or_404(session=session, tenant_id=tenant_id)
    input_data = tenant_in.model_dump(exclude_unset=True)
    update_data = {
        key: value for key, value in input_data.items() if key in TENANT_FIELDS
    }
    if "plan_id" in input_data:
        update_data["plan_id"] = resolve_active_plan(
            session=session,
            plan_id=input_data["plan_id"],
        ).id
    profile = ensure_tenant_profile(session=session, tenant=tenant)
    new_code = update_data.get("code")
    if new_code and new_code != tenant.code:
        existing = session.exec(select(Tenant).where(Tenant.code == new_code)).first()
        if existing is not None:
            raise HTTPException(status_code=409, detail="Tenant code already exists")
    previous_status = effective_lifecycle_status(profile)
    if "is_active" in update_data:
        requested_active = update_data.pop("is_active")
        if not requested_active:
            if previous_status not in {
                TenantLifecycleStatus.FROZEN,
                TenantLifecycleStatus.ARCHIVED,
            }:
                profile.lifecycle_status_before_freeze = previous_status
                profile.lifecycle_status = TenantLifecycleStatus.FROZEN
                profile.frozen_at = get_datetime_utc()
                profile.frozen_reason = (
                    input_data.get("frozen_reason") or "Manual disable"
                )
        elif previous_status == TenantLifecycleStatus.FROZEN:
            restored_status = (
                profile.lifecycle_status_before_freeze or TenantLifecycleStatus.FORMAL
            )
            profile.lifecycle_status = restored_status
            profile.lifecycle_status_before_freeze = None
            profile.frozen_at = None
            profile.frozen_reason = None
    apply_tenant_profile_input(profile=profile, data=input_data)
    current_status = effective_lifecycle_status(profile)
    was_active = tenant.is_active
    tenant.sqlmodel_update(update_data)
    tenant.is_active = current_status in {
        TenantLifecycleStatus.TRIAL,
        TenantLifecycleStatus.FORMAL,
    }
    tenant.updated_at = get_datetime_utc()
    session.add(tenant)
    session.add(profile)
    if was_active and not tenant.is_active:
        revoke_tenant_sessions(session=session, tenant_id=tenant.id)
    session.commit()
    session.refresh(tenant)
    return build_tenant_public(session=session, tenant=tenant)


@router.delete(
    "/{tenant_id}",
    dependencies=[Depends(get_current_active_superuser)],
    status_code=204,
)
def archive_tenant(*, session: SessionDep, tenant_id: uuid.UUID) -> Response:
    ensure_tenant_is_mutable(tenant_id)
    tenant = get_tenant_or_404(session=session, tenant_id=tenant_id)
    profile = ensure_tenant_profile(session=session, tenant=tenant)
    profile.lifecycle_status = TenantLifecycleStatus.ARCHIVED
    profile.lifecycle_status_before_freeze = None
    profile.updated_at = get_datetime_utc()
    tenant.is_active = False
    tenant.updated_at = get_datetime_utc()
    session.add(tenant)
    session.add(profile)
    revoke_tenant_sessions(session=session, tenant_id=tenant.id)
    enqueue_event(
        session=session,
        module_code="platform",
        event_type="platform.tenant.archived",
        tenant_id=tenant.id,
        aggregate_id=str(tenant.id),
        payload={"tenant_id": str(tenant.id), "tenant_code": tenant.code},
    )
    session.commit()
    return Response(status_code=204)
