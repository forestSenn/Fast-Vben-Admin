from fastapi import APIRouter

from app.api.routes import private
from app.core.config import settings
from app.modules.manifest import build_manifest, load_manifest_file
from app.modules.registry import get_module_definitions, get_module_routers


def get_current_manifest():
    if settings.BUILD_MANIFEST_PATH is not None:
        return load_manifest_file(settings.BUILD_MANIFEST_PATH)
    return build_manifest(edition=settings.APP_EDITION)


def create_api_router(*, edition: str | None = None) -> APIRouter:
    manifest = build_manifest(edition=edition) if edition else get_current_manifest()
    definitions = get_module_definitions()
    enabled_definitions = [definitions[module.code] for module in manifest.modules]

    api_router = APIRouter()
    for router in get_module_routers(enabled_definitions):
        api_router.include_router(router)
    if settings.ENVIRONMENT == "local":
        api_router.include_router(private.router)
    return api_router


api_router = create_api_router()
