from collections.abc import Callable

from sqlmodel import Session

from app.core.config import settings

ReferenceGuard = Callable[[Session, str, object, object | None], int]
REFERENCE_GUARDS: dict[str, ReferenceGuard] = {}


class ReferenceGuardUnavailableError(ValueError):
    """Raised when an installed module cannot attest to a destructive action."""


def register_reference_guard(module_code: str, guard: ReferenceGuard) -> None:
    REFERENCE_GUARDS[module_code] = guard


def find_references(
    *, session: Session, reference_type: str, reference_id, tenant_id=None
) -> dict[str, int]:
    """Return reference counts, failing closed for required guards."""
    from app.modules.manifest import build_manifest, load_manifest_file
    from app.modules.registry import get_module_definitions

    manifest = (
        load_manifest_file(settings.BUILD_MANIFEST_PATH)
        if settings.BUILD_MANIFEST_PATH is not None
        else build_manifest(edition=settings.APP_EDITION)
    )
    definitions = get_module_definitions()
    references: dict[str, int] = {}
    for module in manifest.modules:
        definition = definitions[module.code]
        if reference_type not in definition.reference_guards:
            continue
        guard = REFERENCE_GUARDS.get(module.code)
        if guard is None:
            raise ReferenceGuardUnavailableError(
                f"Reference guard unavailable for installed module: {module.code}"
            )
        try:
            count = guard(session, reference_type, reference_id, tenant_id)
        except Exception as exc:
            raise ReferenceGuardUnavailableError(
                f"Reference guard failed for installed module: {module.code}"
            ) from exc
        if count > 0:
            references[module.code] = count
    return references


def assert_no_references(
    *, session: Session, reference_type: str, reference_id, tenant_id=None
) -> None:
    references = find_references(
        session=session,
        reference_type=reference_type,
        reference_id=reference_id,
        tenant_id=tenant_id,
    )
    if references:
        details = ", ".join(f"{module}={count}" for module, count in references.items())
        raise ValueError(f"Master data still has module references: {details}")
