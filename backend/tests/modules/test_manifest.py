from pathlib import Path

import pytest
from fastapi import FastAPI

from app.api.main import create_api_router
from app.models import ModuleDesiredState, ModuleObservedState, ModuleRegistry
from app.modules.access import validate_module_runtime
from app.modules.contracts import MigrationSpec, ModuleDefinition
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


def test_suite_edition_includes_items_module() -> None:
    manifest = build_manifest(edition="suite")
    paths = schema_paths_for("suite")

    assert [module.code for module in manifest.modules] == ["platform", "items"]
    assert "/api/v1/items" in paths
    assert manifest.manifest_digest == manifest_digest(manifest.canonical_payload())


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
