from pathlib import Path

import pytest
from fastapi import FastAPI

from app.api.main import create_api_router
from app.models import ModuleDesiredState, ModuleObservedState, ModuleRegistry
from app.modules.access import validate_module_runtime
from app.modules.contracts import MigrationSpec, ModuleDefinition
from app.modules.events import validate_event_contracts
from app.modules.manifest import (
    build_manifest,
    load_manifest_file,
    manifest_digest,
    resolve_module_definitions,
    write_manifest,
)
from app.modules.registry import get_module_definitions


def schema_paths_for(edition: str) -> set[str]:
    app = FastAPI()
    app.include_router(create_api_router(edition=edition), prefix="/api/v1")
    return set(app.openapi()["paths"])


def test_base_edition_contains_only_platform_routes() -> None:
    paths = schema_paths_for("base")

    assert "/api/v1/platform/modules/manifest" in paths
    assert "/api/v1/items" not in paths


def test_suite_edition_includes_all_delivered_business_modules() -> None:
    manifest = build_manifest(edition="suite")
    paths = schema_paths_for("suite")

    assert [module.code for module in manifest.modules] == ["platform", "items", "erp"]
    assert manifest.schema_version == 2
    assert len(manifest.source_revision) == 40
    assert manifest.modules[0].migration_heads
    assert manifest.modules[0].openapi_sha256.startswith("sha256:")
    assert "/api/v1/items" in paths
    assert "/api/v1/erp/products" in paths
    assert manifest.manifest_digest == manifest_digest(manifest.canonical_payload())

    assert build_manifest(edition="suite") == manifest


def test_erp_edition_includes_only_platform_and_erp_routes() -> None:
    manifest = build_manifest(edition="erp")
    paths = schema_paths_for("erp")

    assert [module.code for module in manifest.modules] == ["platform", "erp"]
    assert "/api/v1/erp/products" in paths
    assert "/api/v1/items" not in paths


def test_manifest_digest_changes_with_module_contract_inputs(monkeypatch) -> None:
    baseline = build_manifest(edition="base")

    monkeypatch.setattr(
        "app.modules.manifest.module_migration_heads", lambda **_kwargs: ["next-head"]
    )
    changed_head = build_manifest(edition="base")

    assert changed_head.manifest_digest != baseline.manifest_digest

    monkeypatch.undo()
    monkeypatch.setattr(
        "app.modules.manifest.module_openapi_sha256",
        lambda _definition: "sha256:changed-contract",
    )
    changed_openapi = build_manifest(edition="base")
    assert changed_openapi.manifest_digest != baseline.manifest_digest


def test_manifest_file_is_verified_against_current_definitions(tmp_path: Path) -> None:
    output = tmp_path / "build-manifest.json"
    expected = write_manifest(edition="suite", output=output)

    assert load_manifest_file(output) == expected

    output.write_text(
        output.read_text(encoding="utf-8").replace('"suite"', '"base"', 1),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="digest"):
        load_manifest_file(output)


def test_manifest_file_load_does_not_require_git_at_runtime(
    monkeypatch, tmp_path: Path
) -> None:
    output = tmp_path / "build-manifest.json"
    expected = write_manifest(edition="base", output=output)

    monkeypatch.setattr(
        "app.modules.manifest.source_revision",
        lambda: (_ for _ in ()).throw(AssertionError("git must not be called")),
    )
    assert load_manifest_file(output) == expected


def test_module_dependency_cycles_are_rejected() -> None:
    definitions = {
        "first": ModuleDefinition(
            code="first",
            version="1.0.0",
            dependencies=("second",),
            routers=(),
            api_prefix="/first",
            permission_prefix="first",
            migration=MigrationSpec(namespace="first", schema="first"),
        ),
        "second": ModuleDefinition(
            code="second",
            version="1.0.0",
            dependencies=("first",),
            routers=(),
            api_prefix="/second",
            permission_prefix="second",
            migration=MigrationSpec(namespace="second", schema="second"),
        ),
    }

    with pytest.raises(ValueError, match="cycle"):
        resolve_module_definitions(["first"], definitions)


def test_edition_fails_closed_when_a_registered_module_is_missing() -> None:
    definitions = {"platform": get_module_definitions()["platform"]}

    with pytest.raises(ValueError, match="unknown module: items"):
        build_manifest(edition="suite", definitions=definitions)


def test_runtime_validation_rejects_enabled_module_absent_from_manifest(db) -> None:
    registry = ModuleRegistry(
        code="unbundled",
        version="1.0.0",
        desired_state=ModuleDesiredState.ENABLED,
        observed_state=ModuleObservedState.READY,
        manifest_digest="sha256:test",
    )
    db.add(registry)
    db.commit()
    try:
        with pytest.raises(RuntimeError, match="unbundled"):
            validate_module_runtime(db)
    finally:
        db.delete(registry)
        db.commit()


def test_platform_event_contracts_cover_published_events() -> None:
    definition = get_module_definitions()["platform"]

    assert {
        (contract.event_type, contract.version, contract.allow_zero_subscribers)
        for contract in definition.event_publishers
    } == {
        ("platform.module.observed_state.changed", 1, True),
        ("platform.department.archived", 1, True),
        ("platform.post.archived", 1, True),
        ("platform.tenant.archived", 1, True),
        ("platform.user.archived", 1, True),
        ("platform.user.anonymized", 1, True),
    }
    validate_event_contracts((definition,))


def test_items_publishes_a_versioned_public_event_contract() -> None:
    definition = get_module_definitions()["items"]

    assert [(event.event_type, event.version) for event in definition.event_publishers] == [
        ("items.item.changed", 1)
    ]
