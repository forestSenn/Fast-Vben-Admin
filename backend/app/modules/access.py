from dataclasses import dataclass
from datetime import datetime

from sqlmodel import Session, col, select

from app.core.config import settings
from app.models import (
    ModuleDesiredState,
    ModuleEntitlementEffect,
    ModuleObservedState,
    ModuleRegistry,
    ModuleStateAudit,
    Tenant,
    TenantModule,
    TenantModuleEntitlementOverride,
    TenantPlan,
    TenantPlanModule,
    User,
    get_datetime_utc,
)


@dataclass(frozen=True)
class ModuleAccessDecision:
    allowed: bool
    error_code: str | None = None


def _current_manifest():
    from app.modules.manifest import build_manifest, load_manifest_file

    if settings.BUILD_MANIFEST_PATH is not None:
        return load_manifest_file(settings.BUILD_MANIFEST_PATH)
    return build_manifest(edition=settings.APP_EDITION)


def ensure_module_runtime(session: Session, *, manifest=None) -> None:
    """Seed missing runtime records without overwriting an operator decision."""
    manifest = manifest or _current_manifest()
    now = get_datetime_utc()
    module_codes = {module.code for module in manifest.modules}

    for module in manifest.modules:
        registry = session.get(ModuleRegistry, module.code)
        if registry is None:
            registry = ModuleRegistry(
                code=module.code,
                version=module.version,
                desired_state=ModuleDesiredState.ENABLED,
                observed_state=ModuleObservedState.BUNDLED,
                manifest_digest=manifest.manifest_digest,
                updated_at=now,
            )
            session.add(registry)
            record_module_state_audit(
                session=session,
                module_code=module.code,
                action="module.observed_state.changed",
                previous_value=None,
                next_value=ModuleObservedState.BUNDLED,
                reason="module bundled in current build manifest",
                actor=None,
            )
        else:
            registry.version = module.version
            registry.manifest_digest = manifest.manifest_digest
            registry.updated_at = now
            session.add(registry)

    # New module editions are entitled for existing plans by default. A later
    # explicit plan mapping or tenant override always takes precedence.
    business_codes = module_codes - {"platform"}
    if business_codes:
        plans = session.exec(select(TenantPlan)).all()
        for plan in plans:
            for module_code in business_codes:
                mapping = session.get(TenantPlanModule, (plan.id, module_code))
                if mapping is None:
                    session.add(
                        TenantPlanModule(
                            plan_id=plan.id,
                            module_code=module_code,
                            is_enabled=True,
                            updated_at=now,
                        )
                    )
    session.flush()


def validate_module_runtime(session: Session, *, manifest=None) -> None:
    """Fail closed when persisted runtime state disagrees with the build."""
    manifest = manifest or _current_manifest()
    manifest_codes = {module.code for module in manifest.modules}
    registries = {
        registry.code: registry for registry in session.exec(select(ModuleRegistry)).all()
    }
    enabled_not_bundled = sorted(
        code
        for code, registry in registries.items()
        if registry.desired_state == ModuleDesiredState.ENABLED
        and code not in manifest_codes
    )
    if enabled_not_bundled:
        raise RuntimeError(
            "Enabled modules are absent from the build manifest: "
            + ", ".join(enabled_not_bundled)
        )
    unavailable = sorted(
        code
        for code in manifest_codes
        if (registry := registries.get(code)) is None
        or (
            registry.desired_state == ModuleDesiredState.ENABLED
            and registry.observed_state != ModuleObservedState.READY
        )
    )
    if unavailable:
        raise RuntimeError(
            "Enabled build modules are not ready: " + ", ".join(unavailable)
        )


def set_module_observed_state(
    *,
    session: Session,
    registry: ModuleRegistry,
    observed_state: ModuleObservedState,
    actual_revision: str | None = None,
    reason: str | None = None,
) -> None:
    """Persist a system-owned lifecycle transition and its audit record."""
    previous_state = registry.observed_state
    registry.observed_state = observed_state
    if actual_revision is not None:
        registry.actual_revision = actual_revision
    registry.updated_at = get_datetime_utc()
    session.add(registry)
    if previous_state != observed_state:
        record_module_state_audit(
            session=session,
            module_code=registry.code,
            action="module.observed_state.changed",
            previous_value=previous_state,
            next_value=observed_state,
            reason=reason,
            actor=None,
        )


def module_for_permission(permission_code: str | None) -> str | None:
    if not permission_code:
        return None
    from app.modules.registry import get_module_definitions

    for definition in get_module_definitions().values():
        if definition.code == "platform":
            continue
        if permission_code.startswith(f"{definition.permission_prefix}:"):
            return definition.code
    return None


def _active_override(
    *, session: Session, tenant_id, module_code: str, now: datetime
) -> TenantModuleEntitlementOverride | None:
    overrides = session.exec(
        select(TenantModuleEntitlementOverride)
        .where(
            TenantModuleEntitlementOverride.tenant_id == tenant_id,
            TenantModuleEntitlementOverride.module_code == module_code,
        )
        .order_by(col(TenantModuleEntitlementOverride.created_at).desc())
    ).all()
    for override in overrides:
        if override.starts_at is not None and override.starts_at > now:
            continue
        if override.ends_at is not None and override.ends_at <= now:
            continue
        return override
    return None


def tenant_has_module_entitlement(
    *, session: Session, tenant: Tenant, module_code: str, now: datetime | None = None
) -> bool:
    now = now or get_datetime_utc()
    plan = session.get(TenantPlan, tenant.plan_id)
    if plan is None or not plan.is_active:
        return False
    override = _active_override(
        session=session,
        tenant_id=tenant.id,
        module_code=module_code,
        now=now,
    )
    if override is not None:
        return override.effect == ModuleEntitlementEffect.GRANT
    mapping = session.get(TenantPlanModule, (tenant.plan_id, module_code))
    return bool(mapping and mapping.is_enabled)


def evaluate_module_access(
    *, session: Session, tenant_id, module_code: str
) -> ModuleAccessDecision:
    manifest = _current_manifest()
    if module_code not in {module.code for module in manifest.modules}:
        return ModuleAccessDecision(False, "MODULE_NOT_INSTALLED")

    ensure_module_runtime(session)
    registry = session.get(ModuleRegistry, module_code)
    if registry is None:
        return ModuleAccessDecision(False, "MODULE_UNAVAILABLE")
    if registry.desired_state != ModuleDesiredState.ENABLED:
        return ModuleAccessDecision(False, "MODULE_UNAVAILABLE")
    if registry.observed_state != ModuleObservedState.READY:
        return ModuleAccessDecision(False, "MODULE_UNAVAILABLE")

    if module_code == "platform":
        return ModuleAccessDecision(True)

    tenant = session.get(Tenant, tenant_id)
    if tenant is None or not tenant.is_active:
        return ModuleAccessDecision(False, "TENANT_MODULE_ENTITLEMENT_REQUIRED")
    if not tenant_has_module_entitlement(
        session=session,
        tenant=tenant,
        module_code=module_code,
    ):
        return ModuleAccessDecision(False, "TENANT_MODULE_ENTITLEMENT_REQUIRED")

    preference = session.get(TenantModule, (tenant_id, module_code))
    if preference is not None and not preference.is_enabled:
        return ModuleAccessDecision(False, "TENANT_MODULE_DISABLED")
    return ModuleAccessDecision(True)


def filter_module_scoped_permissions(
    *, session: Session, tenant_id, permission_codes: list[str]
) -> list[str]:
    decisions: dict[str, bool] = {}
    filtered: list[str] = []
    for permission_code in permission_codes:
        module_code = module_for_permission(permission_code)
        if module_code is None:
            filtered.append(permission_code)
            continue
        if module_code not in decisions:
            decisions[module_code] = evaluate_module_access(
                session=session,
                tenant_id=tenant_id,
                module_code=module_code,
            ).allowed
        if decisions[module_code]:
            filtered.append(permission_code)
    return filtered


def record_module_state_audit(
    *,
    session: Session,
    module_code: str,
    action: str,
    previous_value: str | None,
    next_value: str | None,
    reason: str | None,
    actor: User | None,
    tenant_id=None,
) -> None:
    session.add(
        ModuleStateAudit(
            module_code=module_code,
            tenant_id=tenant_id,
            action=action,
            previous_value=previous_value,
            next_value=next_value,
            reason=reason,
            actor_user_id=actor.id if actor is not None else None,
        )
    )
