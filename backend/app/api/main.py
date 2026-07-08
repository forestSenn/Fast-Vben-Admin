from fastapi import APIRouter

from app.api.routes import (
    departments,
    dictionaries,
    files,
    items,
    login,
    logs,
    menus,
    notices,
    permissions,
    private,
    roles,
    users,
    utils,
)
from app.api.routes import settings as system_settings
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(items.router)
api_router.include_router(logs.router)
api_router.include_router(roles.router)
api_router.include_router(menus.router)
api_router.include_router(notices.router)
api_router.include_router(permissions.router)
api_router.include_router(departments.router)
api_router.include_router(dictionaries.router)
api_router.include_router(system_settings.router)
api_router.include_router(files.router)


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
