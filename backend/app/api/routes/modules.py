import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, select

from app.api.deps import SessionDep, get_current_active_superuser
from app.core.cache import CacheNamespace, redis_cache
from app.core.config import settings
from app.models import (
    ModuleDesiredStateUpdate,
    ModuleRegistry,
    ModuleRegistryPublic,
    OutboxEvent,
    OutboxEventPublic,
    OutboxEventStatus,
    Tenant,
    TenantModule,
    TenantModuleEntitlementOverride,
    TenantModuleEntitlementOverrideCreate,
    TenantModuleUpdate,
    TenantPlan,
    TenantPlanModule,
    TenantPlanModuleUpdate,
    User,
    get_datetime_utc,
)
from app.modules.access import (
    ensure_module_runtime,
    record_module_state_audit,
    tenant_has_module_entitlement,
)
from app.modules.outbox import dispatch_pending_events, requeue_dead_letter

router = APIRouter(prefix="/platform/modules", tags=["platform-modules"])


def current_build_manifest() -> dict[str, Any]:
    from app.modules.manifest import build_manifest, load_manifest_file

    if settings.BUILD_MANIFEST_PATH is not None:
        return load_manifest_file(settings.BUILD_MANIFEST_PATH).public_payload()
    return build_manifest(edition=settings.APP_EDITION).public_payload()


@router.get("/manifest")
def read_build_manifest() -> dict[str, Any]:
    """Return the non-sensitive manifest used to assemble this API."""
    return current_build_manifest()


def get_registry_or_404(*, session: SessionDep, module_code: str) -> ModuleRegistry:
    ensure_module_runtime(session)
    registry = session.get(ModuleRegistry, module_code)
    if registry is None:
        raise HTTPException(status_code=404, detail="Module is not installed")
    return registry


@router.get(
    "",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=list[ModuleRegistryPublic],
)
def read_module_registry(session: SessionDep) -> list[ModuleRegistryPublic]:
    ensure_module_runtime(session)
    modules = session.exec(select(ModuleRegistry).order_by(col(ModuleRegistry.code))).all()
    return [ModuleRegistryPublic.model_validate(module) for module in modules]


@router.patch(
    "/{module_code}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ModuleRegistryPublic,
)
def update_module_desired_state(
    *,
    session: SessionDep,
    current_user: User = Depends(get_current_active_superuser),
    module_code: str,
    body: ModuleDesiredStateUpdate,
) -> ModuleRegistryPublic:
    module = get_registry_or_404(session=session, module_code=module_code)
    previous = module.desired_state
    module.desired_state = body.desired_state
    module.updated_at = get_datetime_utc()
    session.add(module)
    record_module_state_audit(
        session=session,
        module_code=module.code,
        action="module.desired_state.changed",
        previous_value=previous,
        next_value=module.desired_state,
        reason=body.reason,
        actor=current_user,
    )
    session.commit()
    session.refresh(module)
    redis_cache.bump_namespace(CacheNamespace.RBAC)
    return ModuleRegistryPublic.model_validate(module)


@router.put(
    "/plans/{plan_id}/{module_code}",
    dependencies=[Depends(get_current_active_superuser)],
)
def update_plan_module_entitlement(
    *,
    session: SessionDep,
    current_user: User = Depends(get_current_active_superuser),
    plan_id: uuid.UUID,
    module_code: str,
    body: TenantPlanModuleUpdate,
) -> dict[str, Any]:
    get_registry_or_404(session=session, module_code=module_code)
    plan = session.get(TenantPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Tenant plan not found")
    mapping = session.get(TenantPlanModule, (plan_id, module_code))
    previous = mapping.is_enabled if mapping is not None else None
    if mapping is None:
        mapping = TenantPlanModule(plan_id=plan_id, module_code=module_code)
    mapping.is_enabled = body.is_enabled
    mapping.updated_at = get_datetime_utc()
    session.add(mapping)
    record_module_state_audit(
        session=session,
        module_code=module_code,
        action="plan.module_entitlement.changed",
        previous_value=str(previous).lower() if previous is not None else None,
        next_value=str(body.is_enabled).lower(),
        reason=f"plan_id={plan_id}",
        actor=current_user,
    )
    session.commit()
    redis_cache.bump_namespace(CacheNamespace.RBAC)
    return {
        "plan_id": plan_id,
        "module_code": module_code,
        "is_enabled": mapping.is_enabled,
    }


@router.post(
    "/tenants/{tenant_id}/overrides/{module_code}",
    dependencies=[Depends(get_current_active_superuser)],
)
def create_tenant_module_entitlement_override(
    *,
    session: SessionDep,
    current_user: User = Depends(get_current_active_superuser),
    tenant_id: uuid.UUID,
    module_code: str,
    body: TenantModuleEntitlementOverrideCreate,
) -> dict[str, Any]:
    get_registry_or_404(session=session, module_code=module_code)
    if session.get(Tenant, tenant_id) is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if body.ends_at is not None and body.starts_at is not None and body.ends_at <= body.starts_at:
        raise HTTPException(status_code=400, detail="Override end time must be after start time")
    override = TenantModuleEntitlementOverride(
        tenant_id=tenant_id,
        module_code=module_code,
        effect=body.effect,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        reason=body.reason,
        operator_user_id=current_user.id,
    )
    session.add(override)
    record_module_state_audit(
        session=session,
        module_code=module_code,
        tenant_id=tenant_id,
        action="tenant.module_entitlement_override.created",
        previous_value=None,
        next_value=body.effect,
        reason=body.reason,
        actor=current_user,
    )
    session.commit()
    redis_cache.bump_namespace(CacheNamespace.RBAC)
    return {"id": override.id, "tenant_id": tenant_id, "module_code": module_code}


@router.put(
    "/tenants/{tenant_id}/{module_code}",
    dependencies=[Depends(get_current_active_superuser)],
)
def update_tenant_module_preference(
    *,
    session: SessionDep,
    current_user: User = Depends(get_current_active_superuser),
    tenant_id: uuid.UUID,
    module_code: str,
    body: TenantModuleUpdate,
) -> dict[str, Any]:
    get_registry_or_404(session=session, module_code=module_code)
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if body.is_enabled and not tenant_has_module_entitlement(
        session=session,
        tenant=tenant,
        module_code=module_code,
    ):
        raise HTTPException(
            status_code=403, detail="Tenant module entitlement is required"
        )
    preference = session.get(TenantModule, (tenant_id, module_code))
    previous = preference.is_enabled if preference is not None else None
    if preference is None:
        preference = TenantModule(tenant_id=tenant_id, module_code=module_code)
    preference.is_enabled = body.is_enabled
    preference.updated_at = get_datetime_utc()
    session.add(preference)
    record_module_state_audit(
        session=session,
        module_code=module_code,
        tenant_id=tenant_id,
        action="tenant.module_preference.changed",
        previous_value=str(previous).lower() if previous is not None else None,
        next_value=str(body.is_enabled).lower(),
        reason=None,
        actor=current_user,
    )
    session.commit()
    redis_cache.bump_namespace(CacheNamespace.RBAC)
    return {
        "tenant_id": tenant_id,
        "module_code": module_code,
        "is_enabled": preference.is_enabled,
    }


@router.get(
    "/events/dead-letter",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=list[OutboxEventPublic],
)
def read_dead_letter_events(session: SessionDep) -> list[OutboxEventPublic]:
    events = session.exec(
        select(OutboxEvent)
        .where(OutboxEvent.status == OutboxEventStatus.DEAD_LETTER)
        .order_by(col(OutboxEvent.dead_lettered_at).desc())
    ).all()
    return [OutboxEventPublic.model_validate(event) for event in events]


@router.post(
    "/events/{event_id}/retry",
    dependencies=[Depends(get_current_active_superuser)],
)
def retry_dead_letter_event(*, session: SessionDep, event_id: uuid.UUID) -> dict[str, Any]:
    event = session.get(OutboxEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Outbox event not found")
    if event.status != OutboxEventStatus.DEAD_LETTER:
        raise HTTPException(status_code=400, detail="Outbox event is not dead lettered")
    requeue_dead_letter(session=session, event=event)
    session.commit()
    return {"id": event.id, "status": event.status}


@router.post(
    "/events/dispatch",
    dependencies=[Depends(get_current_active_superuser)],
)
def dispatch_events_once(session: SessionDep) -> dict[str, int]:
    delivered, failed = dispatch_pending_events(session=session)
    session.commit()
    return {"delivered": delivered, "failed": failed}
