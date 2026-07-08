from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, func, select

from app.api.deps import SessionDep, require_permission
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
    group: str | None = None,
    page: int = 1,
    page_size: int = 50,
    keyword: str | None = None,
) -> Any:
    filters = []
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
def read_public_settings(session: SessionDep) -> Any:
    settings = session.exec(
        select(SystemSetting)
        .where(SystemSetting.is_public)
        .order_by(col(SystemSetting.group), col(SystemSetting.key))
    ).all()
    return [SystemSettingPublic.model_validate(setting) for setting in settings]


@router.patch(
    "/{key}",
    dependencies=[Depends(require_permission("system:setting:update"))],
    response_model=SystemSettingPublic,
)
def update_setting(
    *, session: SessionDep, key: str, setting_in: SystemSettingUpdate
) -> Any:
    setting = session.exec(select(SystemSetting).where(SystemSetting.key == key)).first()
    if not setting:
        raise HTTPException(status_code=404, detail="System setting not found")

    update_data = setting_in.model_dump(exclude_unset=True)
    if setting.is_system:
        update_data.pop("is_system", None)
    setting.sqlmodel_update(update_data)
    setting.updated_at = get_datetime_utc()
    session.add(setting)
    session.commit()
    session.refresh(setting)
    return setting
