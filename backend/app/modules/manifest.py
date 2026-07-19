import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from app.modules.capabilities import validate_capability_requirements
from app.modules.contracts import ModuleDefinition
from app.modules.registry import get_module_definitions

EDITION_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")


class ManifestModule(BaseModel):
    code: str
    version: str


class BuildManifest(BaseModel):
    edition: str
    platform_version: str
    modules: list[ManifestModule] = Field(default_factory=list)
    manifest_digest: str

    def canonical_payload(self) -> dict[str, object]:
        return {
            "edition": self.edition,
            "platform_version": self.platform_version,
            "modules": [module.model_dump() for module in self.modules],
        }

    def public_payload(self) -> dict[str, object]:
        return self.model_dump()


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def editions_directory() -> Path:
    return repository_root() / "editions"


def _canonical_json(payload: Mapping[str, object]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def manifest_digest(payload: Mapping[str, object]) -> str:
    return f"sha256:{hashlib.sha256(_canonical_json(payload)).hexdigest()}"


def load_edition_modules(*, edition: str, directory: Path | None = None) -> list[str]:
    if not EDITION_NAME_PATTERN.fullmatch(edition):
        raise ValueError(f"Invalid edition name: {edition!r}")

    edition_path = (directory or editions_directory()) / f"{edition}.yaml"
    if not edition_path.is_file():
        raise ValueError(f"Edition file does not exist: {edition_path}")

    loaded = yaml.safe_load(edition_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Edition file must contain an object: {edition_path}")
    if loaded.get("name") != edition:
        raise ValueError(f"Edition name does not match its filename: {edition_path}")

    modules = loaded.get("modules")
    if not isinstance(modules, list) or not modules or not all(
        isinstance(module, str) for module in modules
    ):
        raise ValueError(f"Edition modules must be a non-empty list: {edition_path}")
    if len(modules) != len(set(modules)):
        raise ValueError(f"Edition contains duplicate modules: {edition_path}")
    return modules


def resolve_module_definitions(
    module_codes: list[str],
    definitions: Mapping[str, ModuleDefinition] | None = None,
) -> list[ModuleDefinition]:
    available = definitions or get_module_definitions()
    resolved: list[ModuleDefinition] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(code: str) -> None:
        if code in visited:
            return
        if code in visiting:
            raise ValueError(f"Module dependency cycle detected at: {code}")
        definition = available.get(code)
        if definition is None:
            raise ValueError(f"Edition references an unknown module: {code}")
        visiting.add(code)
        for dependency in definition.dependencies:
            visit(dependency)
        visiting.remove(code)
        visited.add(code)
        resolved.append(definition)

    for module_code in module_codes:
        visit(module_code)
    return resolved


def build_manifest(
    *,
    edition: str,
    directory: Path | None = None,
    definitions: Mapping[str, ModuleDefinition] | None = None,
) -> BuildManifest:
    module_codes = load_edition_modules(edition=edition, directory=directory)
    resolved = resolve_module_definitions(module_codes, definitions)
    validate_capability_requirements(resolved)
    platform = next((definition for definition in resolved if definition.code == "platform"), None)
    if platform is None:
        raise ValueError("Every edition must include the platform module")

    payload: dict[str, object] = {
        "edition": edition,
        "platform_version": platform.version,
        "modules": [
            {"code": definition.code, "version": definition.version}
            for definition in resolved
        ],
    }
    return BuildManifest(**payload, manifest_digest=manifest_digest(payload))


def load_manifest_file(path: Path) -> BuildManifest:
    try:
        manifest = BuildManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Unable to read build manifest: {path}") from exc

    expected_digest = manifest_digest(manifest.canonical_payload())
    if manifest.manifest_digest != expected_digest:
        raise ValueError(f"Build manifest digest does not match: {path}")

    expected = build_manifest(edition=manifest.edition)
    if manifest != expected:
        raise ValueError(f"Build manifest does not match the current module definitions: {path}")
    return manifest


def write_manifest(*, edition: str, output: Path) -> BuildManifest:
    manifest = build_manifest(edition=edition)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest.public_payload(), ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest
