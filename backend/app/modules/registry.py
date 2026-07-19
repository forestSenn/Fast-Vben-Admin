from collections.abc import Iterable

from fastapi import APIRouter

from app.modules.contracts import ModuleDefinition
from app.modules.items.module import definition as items_definition
from app.modules.platform import definition as platform_definition

MODULE_DEFINITIONS: dict[str, ModuleDefinition] = {
    platform_definition.code: platform_definition,
    items_definition.code: items_definition,
}


def get_module_definitions() -> dict[str, ModuleDefinition]:
    return MODULE_DEFINITIONS.copy()


def get_module_routers(
    definitions: Iterable[ModuleDefinition],
) -> tuple[APIRouter, ...]:
    return tuple(router for definition in definitions for router in definition.routers)
