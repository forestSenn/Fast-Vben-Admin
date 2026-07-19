import pytest
from sqlmodel import Session, select

from app.models import CapabilityBindingStatus, Tenant
from app.modules.capabilities import (
    CapabilityConfigurationError,
    bind_capability_provider,
    build_capability_registry,
    close_capability_binding,
    select_capability_provider,
    validate_capability_requirements,
)
from app.modules.contracts import (
    CapabilityProvision,
    CapabilityRequirement,
    MigrationSpec,
    ModuleDefinition,
)


def module_definition(
    code: str,
    *,
    requirements: tuple[CapabilityRequirement, ...] = (),
    provisions: tuple[CapabilityProvision, ...] = (),
) -> ModuleDefinition:
    return ModuleDefinition(
        code=code,
        version="1.0.0",
        dependencies=(),
        routers=(),
        api_prefix=f"/api/v1/{code}",
        permission_prefix=code,
        migration=MigrationSpec(namespace=code, schema=code),
        optional_capabilities=requirements,
        provided_capabilities=provisions,
    )


def test_capability_registry_requires_explicit_selection_when_multiple_providers() -> None:
    requirement = CapabilityRequirement("workflow.approval", 1)
    simple = module_definition(
        "erp",
        provisions=(CapabilityProvision("workflow.approval", 1),),
    )
    advanced = module_definition(
        "ioa",
        provisions=(CapabilityProvision("workflow.approval", 1),),
    )
    registry = build_capability_registry((simple, advanced))

    with pytest.raises(CapabilityConfigurationError, match="multiple providers"):
        select_capability_provider(registry=registry, requirement=requirement)

    selected = select_capability_provider(
        registry=registry,
        requirement=requirement,
        provider_code="ioa",
    )
    assert selected is not None
    assert selected.provider_code == "ioa"
    assert selected.provider_version == "1.0.0"


def test_optional_capability_can_be_absent_but_required_capability_fails_closed() -> None:
    optional = module_definition(
        "erp",
        requirements=(CapabilityRequirement("workflow.approval", 1),),
    )
    required = module_definition(
        "erp",
        requirements=(CapabilityRequirement("workflow.approval", 1, required=True),),
    )

    validate_capability_requirements((optional,))
    assert (
        select_capability_provider(
            registry=build_capability_registry((optional,)),
            requirement=optional.optional_capabilities[0],
        )
        is None
    )
    with pytest.raises(CapabilityConfigurationError, match="requires unavailable"):
        validate_capability_requirements((required,))


def test_capability_provider_binding_is_immutable(db: Session) -> None:
    tenant = db.exec(select(Tenant).where(Tenant.code == "default")).first()
    assert tenant is not None
    tenant_id = tenant.id
    binding = bind_capability_provider(
        session=db,
        tenant_id=tenant_id,
        consumer_module="erp",
        aggregate_type="purchase_order",
        aggregate_id="po-1",
        capability_code="workflow.approval",
        provider_code="ioa",
        provider_version="1",
        external_instance_id="approval-1",
    )
    db.commit()
    assert (
        bind_capability_provider(
            session=db,
            tenant_id=tenant_id,
            consumer_module="erp",
            aggregate_type="purchase_order",
            aggregate_id="po-1",
            capability_code="workflow.approval",
            provider_code="ioa",
            provider_version="1",
            external_instance_id="approval-1",
        ).id
        == binding.id
    )
    with pytest.raises(ValueError, match="cannot be changed"):
        bind_capability_provider(
            session=db,
            tenant_id=tenant_id,
            consumer_module="erp",
            aggregate_type="purchase_order",
            aggregate_id="po-1",
            capability_code="workflow.approval",
            provider_code="simple",
            provider_version="1",
        )
    close_capability_binding(session=db, binding=binding)
    db.commit()
    assert binding.status == CapabilityBindingStatus.CLOSED
