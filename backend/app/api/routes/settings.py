import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, func, select

from app.api.deps import (
    CurrentTenant,
    PublicTenantId,
    SessionDep,
    normalize_pagination,
    require_permission,
)
from app.core.cache import CacheNamespace, redis_cache
from app.models import (
    SystemSetting,
    SystemSettingPublic,
    SystemSettingsPublic,
    SystemSettingUpdate,
    get_datetime_utc,
)

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get(
    "",
    dependencies=[Depends(require_permission("system:setting:list"))],
    response_model=SystemSettingsPublic,
)
def read_settings(
    session: SessionDep,
    tenant_context: CurrentTenant,
    group: str | None = None,
    page: int = 1,
    page_size: int = 50,
    keyword: str | None = None,
) -> Any:
    page, page_size = normalize_pagination(page=page, page_size=page_size)
    filters = [SystemSetting.tenant_id == tenant_context.tenant_id]
    if group:
        filters.append(SystemSetting.group == group)
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            (col(SystemSetting.key).ilike(pattern))
            | (col(SystemSetting.name).ilike(pattern))
        )

    count_statement = select(func.count()).select_from(SystemSetting)
    if filters:
        count_statement = count_statement.where(*filters)
    count = session.exec(count_statement).one()

    statement = select(SystemSetting)
    if filters:
        statement = statement.where(*filters)
    statement = (
        statement.order_by(col(SystemSetting.group), col(SystemSetting.key))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    settings = session.exec(statement).all()
    return SystemSettingsPublic(
        items=[SystemSettingPublic.model_validate(setting) for setting in settings],
        total=count,
        page=page,
        page_size=page_size,
    )


@router.get("/public", response_model=list[SystemSettingPublic])
def read_public_settings(
    session: SessionDep,
    public_tenant_id: PublicTenantId,
) -> Any:
    cache_key = redis_cache.build_versioned_key(
        CacheNamespace.PUBLIC_SETTINGS,
        str(public_tenant_id),
        "all",
    )
    cached_settings = redis_cache.get_json(cache_key)
    if cached_settings is not None:
        return [
            SystemSettingPublic.model_validate(setting) for setting in cached_settings
        ]

    settings = session.exec(
        select(SystemSetting)
        .where(
            SystemSetting.tenant_id == public_tenant_id,
            SystemSetting.is_public,
        )
        .order_by(col(SystemSetting.group), col(SystemSetting.key))
    ).all()
    public_settings = [
        SystemSettingPublic.model_validate(setting) for setting in settings
    ]
    redis_cache.set_json(
        cache_key,
        [setting.model_dump(mode="json") for setting in public_settings],
    )
    return public_settings


@router.patch(
    "/{key}",
    dependencies=[Depends(require_permission("system:setting:update"))],
    response_model=SystemSettingPublic,
)
def update_setting(
    *,
    session: SessionDep,
    tenant_context: CurrentTenant,
    key: str,
    setting_in: SystemSettingUpdate,
) -> Any:
    setting = session.exec(
        select(SystemSetting).where(
            SystemSetting.tenant_id == tenant_context.tenant_id,
            SystemSetting.key == key,
        )
    ).first()
    if not setting:
        raise HTTPException(status_code=404, detail="System setting not found")

    update_data = setting_in.model_dump(exclude_unset=True)
    if setting.is_system:
        update_data.pop("is_system", None)
    next_value_type = update_data.get("value_type", setting.value_type)
    next_value = update_data.get("value", setting.value)
    if next_value_type == "json":
        try:
            json.loads(next_value)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Setting value must be JSON")
    setting.sqlmodel_update(update_data)
    setting.updated_at = get_datetime_utc()
    session.add(setting)
    session.commit()
    session.refresh(setting)
    redis_cache.bump_namespace(CacheNamespace.PUBLIC_SETTINGS)
    return setting
