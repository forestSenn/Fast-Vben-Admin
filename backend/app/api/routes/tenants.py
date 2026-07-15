import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlmodel import col, func, or_, select

from app.api.deps import (
    CurrentTenant,
    CurrentTokenPayload,
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
    normalize_pagination,
)
from app.api.routes.login import create_login_token
from app.core.db import provision_tenant_roles
from app.core.quotas import get_file_usage, get_member_count
from app.core.tenancy import DEFAULT_TENANT_ID
from app.models import (
    Tenant,
    TenantCreate,
    TenantInitializationTemplate,
    TenantInitializationTemplateCreate,
    TenantInitializationTemplatePublic,
    TenantInitializationTemplatesPublic,
    TenantInitializationTemplateUpdate,
    TenantMembership,
    TenantMembershipPublic,
    TenantPlan,
    TenantPlanCreate,
    TenantPlanPublic,
    TenantPlansPublic,
    TenantPlanUpdate,
    TenantPublic,
    TenantsPublic,
    TenantSwitchRequest,
    TenantUpdate,
    TenantUsagePublic,
    Token,
    UserSession,
    get_datetime_utc,
)

router = APIRouter(prefix="/tenants", tags=["tenants"])


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
    return TenantPublic.model_validate(
        tenant,
        update={
            "plan_name": plan.name if plan is not None else None,
            "initialization_template_name": (
                template.name if template is not None else None
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
) -> Any:
    page, page_size = normalize_pagination(page=page, page_size=page_size)
    filters = []
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            or_(col(Tenant.code).ilike(pattern), col(Tenant.name).ilike(pattern))
        )
    if is_active is not None:
        filters.append(Tenant.is_active == is_active)
    count = session.exec(select(func.count()).select_from(Tenant).where(*filters)).one()
    tenants = session.exec(
        select(Tenant)
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
    count = session.exec(
        select(func.count()).select_from(TenantPlan).where(*filters)
    ).one()
    plans = session.exec(
        select(TenantPlan)
        .where(*filters)
        .order_by(col(TenantPlan.is_default).desc(), col(TenantPlan.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return TenantPlansPublic(
        items=[TenantPlanPublic.model_validate(plan) for plan in plans],
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
    return [TenantPlanPublic.model_validate(plan) for plan in plans]


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
    plan = TenantPlan.model_validate(plan_in)
    if plan.is_default:
        set_default_plan(session=session, plan=plan)
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return TenantPlanPublic.model_validate(plan)


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
    update_data = plan_in.model_dump(exclude_unset=True)
    new_code = update_data.get("code")
    if new_code and new_code != plan.code:
        existing = session.exec(
            select(TenantPlan).where(TenantPlan.code == new_code)
        ).first()
        if existing is not None:
            raise HTTPException(
                status_code=409, detail="Tenant plan code already exists"
            )
    if plan.is_default and update_data.get("is_default") is False:
        raise HTTPException(
            status_code=400, detail="Default tenant plan cannot be unset"
        )
    if plan.is_default and update_data.get("is_active") is False:
        raise HTTPException(
            status_code=400, detail="Default tenant plan cannot be disabled"
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
    session.commit()
    session.refresh(plan)
    return TenantPlanPublic.model_validate(plan)


@router.delete(
    "/plans/{plan_id}",
    dependencies=[Depends(get_current_active_superuser)],
    status_code=204,
)
def delete_tenant_plan(*, session: SessionDep, plan_id: uuid.UUID) -> Response:
    plan = get_plan_or_404(session=session, plan_id=plan_id)
    if plan.is_default:
        raise HTTPException(
            status_code=400, detail="Default tenant plan cannot be deleted"
        )
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
    plan = resolve_active_plan(session=session, plan_id=tenant_in.plan_id)
    template = resolve_active_template(
        session=session,
        template_id=tenant_in.initialization_template_id,
    )
    tenant = Tenant.model_validate(
        tenant_in,
        update={
            "plan_id": plan.id,
            "initialization_template_id": template.id,
        },
    )
    session.add(tenant)
    session.flush()
    provision_tenant_roles(
        session=session,
        tenant=tenant,
        template=template,
        owner=current_user,
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
        plan=TenantPlanPublic.model_validate(plan),
        members=get_member_count(session=session, tenant_id=tenant.id),
        file_assets=file_assets,
        storage_bytes=storage_bytes,
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
    tenant = get_tenant_or_404(session=session, tenant_id=tenant_id)
    update_data = tenant_in.model_dump(exclude_unset=True)
    if "plan_id" in update_data:
        update_data["plan_id"] = resolve_active_plan(
            session=session,
            plan_id=update_data["plan_id"],
        ).id
    if tenant.id == DEFAULT_TENANT_ID:
        if update_data.get("is_active") is False:
            raise HTTPException(
                status_code=400, detail="Default tenant cannot be disabled"
            )
        if "code" in update_data and update_data["code"] != tenant.code:
            raise HTTPException(
                status_code=400, detail="Default tenant code cannot be changed"
            )
    new_code = update_data.get("code")
    if new_code and new_code != tenant.code:
        existing = session.exec(select(Tenant).where(Tenant.code == new_code)).first()
        if existing is not None:
            raise HTTPException(status_code=409, detail="Tenant code already exists")
    was_active = tenant.is_active
    tenant.sqlmodel_update(update_data)
    tenant.updated_at = get_datetime_utc()
    session.add(tenant)
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
    if tenant_id == DEFAULT_TENANT_ID:
        raise HTTPException(status_code=400, detail="Default tenant cannot be disabled")
    tenant = get_tenant_or_404(session=session, tenant_id=tenant_id)
    tenant.is_active = False
    tenant.updated_at = get_datetime_utc()
    session.add(tenant)
    revoke_tenant_sessions(session=session, tenant_id=tenant.id)
    session.commit()
    return Response(status_code=204)
