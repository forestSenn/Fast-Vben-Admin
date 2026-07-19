from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from sqlmodel import Session, select

from app.models import CapabilityBinding, CapabilityBindingStatus, get_datetime_utc
from app.modules.contracts import CapabilityRequirement, ModuleDefinition


class CapabilityConfigurationError(ValueError):
    """Raised when the composition root cannot bind a declared capability."""


@dataclass(frozen=True)
class ResolvedCapabilityProvider:
    """A provider selected from module declarations by the composition root."""

    code: str
    major_version: int
    provider_code: str
    provider_version: str


CapabilityRegistry = Mapping[
    tuple[str, int], tuple[ResolvedCapabilityProvider, ...]
]


def build_capability_registry(
    definitions: Iterable[ModuleDefinition],
) -> dict[tuple[str, int], tuple[ResolvedCapabilityProvider, ...]]:
    """Collect providers from the enabled edition without importing modules dynamically."""
    providers: dict[tuple[str, int], list[ResolvedCapabilityProvider]] = {}
    for definition in definitions:
        for provision in definition.provided_capabilities:
            key = (provision.code, provision.major_version)
            provider = ResolvedCapabilityProvider(
                code=provision.code,
                major_version=provision.major_version,
                provider_code=definition.code,
                provider_version=definition.version,
            )
            entries = providers.setdefault(key, [])
            if any(entry.provider_code == definition.code for entry in entries):
                raise CapabilityConfigurationError(
                    f"Module {definition.code} declares capability {provision.code} "
                    f"v{provision.major_version} more than once"
                )
            entries.append(provider)
    return {
        key: tuple(sorted(entries, key=lambda entry: entry.provider_code))
        for key, entries in providers.items()
    }


def validate_capability_requirements(
    definitions: Iterable[ModuleDefinition],
    registry: CapabilityRegistry | None = None,
) -> None:
    """Fail closed only for required capabilities; optional capabilities may degrade."""
    resolved_definitions = tuple(definitions)
    registry = registry or build_capability_registry(resolved_definitions)
    for definition in resolved_definitions:
        for requirement in definition.optional_capabilities:
            if requirement.required and not registry.get(
                (requirement.code, requirement.major_version)
            ):
                raise CapabilityConfigurationError(
                    f"Module {definition.code} requires unavailable capability "
                    f"{requirement.code} v{requirement.major_version}"
                )


def select_capability_provider(
    *,
    registry: CapabilityRegistry,
    requirement: CapabilityRequirement,
    provider_code: str | None = None,
) -> ResolvedCapabilityProvider | None:
    """Select a provider explicitly; ambiguous optional capabilities never auto-bind."""
    providers = registry.get((requirement.code, requirement.major_version), ())
    if provider_code is not None:
        for provider in providers:
            if provider.provider_code == provider_code:
                return provider
        raise CapabilityConfigurationError(
            f"Capability provider {provider_code} is unavailable for "
            f"{requirement.code} v{requirement.major_version}"
        )
    if not providers:
        if requirement.required:
            raise CapabilityConfigurationError(
                f"Required capability {requirement.code} v{requirement.major_version} "
                "has no provider"
            )
        return None
    if len(providers) > 1:
        raise CapabilityConfigurationError(
            f"Capability {requirement.code} v{requirement.major_version} has multiple "
            "providers; the composition root must choose one"
        )
    return providers[0]


def bind_capability_provider(
    *,
    session: Session,
    tenant_id,
    consumer_module: str,
    aggregate_type: str,
    aggregate_id: str,
    capability_code: str,
    provider_code: str,
    provider_version: str,
    external_instance_id: str | None = None,
) -> CapabilityBinding:
    """Persist the provider selected for an in-flight business instance."""
    existing = session.exec(
        select(CapabilityBinding).where(
            CapabilityBinding.tenant_id == tenant_id,
            CapabilityBinding.consumer_module == consumer_module,
            CapabilityBinding.aggregate_type == aggregate_type,
            CapabilityBinding.aggregate_id == aggregate_id,
            CapabilityBinding.capability_code == capability_code,
        )
    ).first()
    if existing is not None:
        if (
            existing.provider_code != provider_code
            or existing.provider_version != provider_version
            or existing.external_instance_id != external_instance_id
        ):
            raise ValueError("Capability provider binding cannot be changed in place")
        return existing
    binding = CapabilityBinding(
        tenant_id=tenant_id,
        consumer_module=consumer_module,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        capability_code=capability_code,
        provider_code=provider_code,
        provider_version=provider_version,
        external_instance_id=external_instance_id,
        created_at=get_datetime_utc(),
    )
    session.add(binding)
    return binding


def close_capability_binding(*, session: Session, binding: CapabilityBinding) -> None:
    binding.status = CapabilityBindingStatus.CLOSED
    binding.closed_at = get_datetime_utc()
    session.add(binding)
