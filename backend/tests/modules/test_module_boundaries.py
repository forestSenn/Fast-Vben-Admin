import ast
from dataclasses import is_dataclass
from pathlib import Path

from app.modules.registry import get_module_definitions

BACKEND_ROOT = Path(__file__).resolve().parents[2]
MODULES_ROOT = BACKEND_ROOT / "app" / "modules"
IMPLEMENTATION_SEGMENTS = {
    "application",
    "domain",
    "infrastructure",
    "migrations",
    "routes",
}
SHARED_MODULE_PACKAGES = {
    "access",
    "capabilities",
    "contracts",
    "manifest",
    "migrations",
    "outbox",
    "references",
    "registry",
}


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    return modules


def business_module_roots() -> list[Path]:
    return sorted(
        path
        for path in MODULES_ROOT.iterdir()
        if path.is_dir() and (path / "module.py").is_file()
    )


def test_business_modules_do_not_import_platform_orm_or_legacy_web_adapters() -> None:
    forbidden_prefixes = ("app.models", "app.api", "app.crud")
    violations: list[str] = []
    for module_root in business_module_roots():
        for path in module_root.rglob("*.py"):
            for module in imported_modules(path):
                if module.startswith(forbidden_prefixes):
                    violations.append(f"{path.relative_to(BACKEND_ROOT)} -> {module}")
    assert not violations, "\n".join(violations)


def test_business_modules_only_use_platform_public_contracts() -> None:
    allowed_prefixes = ("app.platform.public_api", "app.platform.web_api")
    violations: list[str] = []
    for module_root in business_module_roots():
        for path in module_root.rglob("*.py"):
            for module in imported_modules(path):
                if module.startswith("app.platform") and not module.startswith(
                    allowed_prefixes
                ):
                    violations.append(f"{path.relative_to(BACKEND_ROOT)} -> {module}")
    assert not violations, "\n".join(violations)


def test_platform_core_does_not_import_business_module_implementation() -> None:
    violations: list[str] = []
    for root in [BACKEND_ROOT / "app" / "core", BACKEND_ROOT / "app" / "api" / "routes"]:
        for path in root.rglob("*.py"):
            for module in imported_modules(path):
                for module_root in business_module_roots():
                    if module.startswith(f"app.modules.{module_root.name}"):
                        violations.append(f"{path.relative_to(BACKEND_ROOT)} -> {module}")
    assert not violations, "\n".join(violations)


def test_public_api_does_not_import_module_implementation_or_web_framework() -> None:
    violations: list[str] = []
    for module_root in business_module_roots():
        for path in module_root.joinpath("public_api").rglob("*.py"):
            for module in imported_modules(path):
                internal_import = module.startswith(f"app.modules.{module_root.name}.") and any(
                    f".{segment}" in module for segment in IMPLEMENTATION_SEGMENTS
                )
                framework_import = module.startswith(("fastapi", "sqlalchemy", "sqlmodel"))
                if internal_import or framework_import:
                    violations.append(f"{path.relative_to(BACKEND_ROOT)} -> {module}")
    assert not violations, "\n".join(violations)


def test_module_imports_match_declared_dependencies() -> None:
    definitions = get_module_definitions()
    violations: list[str] = []
    for source_code, definition in definitions.items():
        source_root = MODULES_ROOT / source_code
        if not source_root.is_dir():
            continue
        for path in source_root.rglob("*.py"):
            for module in imported_modules(path):
                parts = module.split(".")
                if len(parts) < 3 or parts[:2] != ["app", "modules"]:
                    continue
                target_code = parts[2]
                if target_code in SHARED_MODULE_PACKAGES:
                    continue
                if target_code == source_code:
                    continue
                dependency_is_declared = target_code in definition.dependencies
                uses_public_contract = len(parts) >= 4 and parts[3] == "public_api"
                if not dependency_is_declared or not uses_public_contract:
                    violations.append(
                        f"{path.relative_to(BACKEND_ROOT)}: {source_code} -> {module} "
                        f"(dependency declared={dependency_is_declared})"
                    )
    assert not violations, "\n".join(violations)


def test_platform_web_api_exposes_immutable_contexts() -> None:
    from inspect import signature

    from app.platform.web_api import (
        Principal,
        TenantContext,
        build_owner_data_scope_filter,
    )

    assert is_dataclass(Principal) and Principal.__dataclass_params__.frozen
    assert is_dataclass(TenantContext) and TenantContext.__dataclass_params__.frozen
    assert "current_principal" in signature(build_owner_data_scope_filter).parameters
