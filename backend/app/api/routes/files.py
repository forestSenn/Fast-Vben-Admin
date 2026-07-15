import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import col, func, or_, select

from app.api.deps import (
    CurrentTenant,
    CurrentUser,
    OptionalCurrentUser,
    OptionalTenantId,
    SessionDep,
    normalize_pagination,
    require_permission,
)
from app.core.quotas import ensure_file_quota
from app.models import (
    FileAsset,
    FileAssetPublic,
    FileAssetsPublic,
    FileDownloadUrl,
    FileStorageChannel,
    FileStorageChannelCreate,
    FileStorageChannelPublic,
    FileStorageChannelsPublic,
    FileStorageChannelUpdate,
    StorageConfigPublic,
    SystemSetting,
    UploadConfigPublic,
    UploadConfigUpdate,
    UserPublic,
    get_datetime_utc,
)
from app.storage import (
    _ensure_s3_bucket,
    _get_s3_client,
    delete_stored_file,
    get_default_storage_channel,
    get_file_download_response,
    get_presigned_download_url,
    get_presigned_url_expire_seconds,
    get_upload_allowed_extensions,
    get_upload_default_public,
    get_upload_max_size_mb,
    save_upload_file,
)

router = APIRouter(prefix="/files", tags=["files"])


def mask_storage_channel(channel: FileStorageChannel) -> FileStorageChannelPublic:
    data = FileStorageChannelPublic.model_validate(channel)
    if data.secret_access_key:
        data.secret_access_key = "******"
    return data


def ensure_supported_provider(provider: str) -> None:
    if provider not in {"local", "s3"}:
        raise HTTPException(status_code=400, detail="Unsupported storage provider")


def ensure_channel_code_unique(
    *,
    session: SessionDep,
    tenant_id: uuid.UUID,
    code: str,
    exclude_id: uuid.UUID | None = None,
) -> None:
    statement = select(FileStorageChannel).where(
        FileStorageChannel.tenant_id == tenant_id,
        FileStorageChannel.code == code,
    )
    if exclude_id:
        statement = statement.where(FileStorageChannel.id != exclude_id)
    if session.exec(statement).first():
        raise HTTPException(
            status_code=409, detail="Storage channel code already exists"
        )


def clear_default_storage_channels(
    *,
    session: SessionDep,
    tenant_id: uuid.UUID,
    exclude_id: uuid.UUID | None = None,
) -> None:
    statement = select(FileStorageChannel).where(
        FileStorageChannel.tenant_id == tenant_id,
        FileStorageChannel.is_default,
    )
    if exclude_id:
        statement = statement.where(FileStorageChannel.id != exclude_id)
    for channel in session.exec(statement).all():
        channel.is_default = False
        channel.updated_at = get_datetime_utc()
        session.add(channel)


def ensure_upload_setting(
    *,
    session: SessionDep,
    tenant_id: uuid.UUID,
    key: str,
    name: str,
    value: str,
    value_type: str,
) -> SystemSetting:
    setting = session.exec(
        select(SystemSetting).where(
            SystemSetting.tenant_id == tenant_id,
            SystemSetting.key == key,
        )
    ).first()
    if not setting:
        setting = SystemSetting(
            tenant_id=tenant_id,
            key=key,
            name=name,
            value=value,
            value_type=value_type,
            group="upload",
            is_public=False,
            is_system=True,
        )
    else:
        setting.value = value
        setting.value_type = value_type
        setting.updated_at = get_datetime_utc()
    session.add(setting)
    return setting


@router.get(
    "",
    dependencies=[Depends(require_permission("system:file:list"))],
    response_model=FileAssetsPublic,
)
def read_files(
    session: SessionDep,
    tenant_context: CurrentTenant,
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    storage_provider: str | None = None,
    is_public: bool | None = None,
) -> Any:
    page, page_size = normalize_pagination(page=page, page_size=page_size)
    filters = [FileAsset.tenant_id == tenant_context.tenant_id]
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            or_(
                col(FileAsset.original_name).ilike(pattern),
                col(FileAsset.content_type).ilike(pattern),
                col(FileAsset.extension).ilike(pattern),
            )
        )
    if storage_provider:
        filters.append(FileAsset.storage_provider == storage_provider)
    if is_public is not None:
        filters.append(FileAsset.is_public == is_public)

    count_statement = select(func.count()).select_from(FileAsset)
    if filters:
        count_statement = count_statement.where(*filters)
    count = session.exec(count_statement).one()

    statement = select(FileAsset)
    if filters:
        statement = statement.where(*filters)
    statement = (
        statement.order_by(col(FileAsset.created_at).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    files = session.exec(statement).all()
    return FileAssetsPublic(
        items=[FileAssetPublic.model_validate(file_asset) for file_asset in files],
        total=count,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/upload",
    dependencies=[Depends(require_permission("system:file:upload"))],
    response_model=FileAssetPublic,
)
def upload_file(
    session: SessionDep,
    current_user: CurrentUser,
    tenant_context: CurrentTenant,
    file: UploadFile = File(...),
    is_public: bool | None = None,
) -> Any:
    stored_file = save_upload_file(
        file,
        session=session,
        tenant_id=tenant_context.tenant_id,
    )
    try:
        ensure_file_quota(
            session=session,
            tenant_id=tenant_context.tenant_id,
            incoming_size=stored_file.size,
        )
    except HTTPException:
        delete_stored_file(
            stored_file.storage_provider,
            stored_file.storage_path,
            session,
            tenant_context.tenant_id,
        )
        raise
    file_asset = FileAsset(
        tenant_id=tenant_context.tenant_id,
        original_name=stored_file.original_name,
        stored_name=stored_file.stored_name,
        content_type=stored_file.content_type,
        extension=stored_file.extension,
        size=stored_file.size,
        sha256=stored_file.sha256,
        storage_provider=stored_file.storage_provider,
        storage_path=stored_file.storage_path,
        public_url=None,
        uploader_id=current_user.id,
        is_public=(
            is_public
            if is_public is not None
            else get_upload_default_public(session, tenant_context.tenant_id)
        ),
    )
    session.add(file_asset)
    session.commit()
    session.refresh(file_asset)
    file_asset.public_url = f"/api/v1/files/{file_asset.id}/download"
    session.add(file_asset)
    session.commit()
    session.refresh(file_asset)
    return file_asset


@router.get(
    "/storage-config",
    dependencies=[Depends(require_permission("system:file:list"))],
    response_model=StorageConfigPublic,
)
def read_storage_config(
    session: SessionDep,
    tenant_context: CurrentTenant,
) -> StorageConfigPublic:
    channel = get_default_storage_channel(session, tenant_context.tenant_id)
    return StorageConfigPublic(
        provider=channel.provider,
        channel_id=channel.id,
        channel_name=channel.name,
        max_size_mb=get_upload_max_size_mb(session, tenant_context.tenant_id),
        allowed_extensions=get_upload_allowed_extensions(
            session,
            tenant_context.tenant_id,
        ),
        default_public=get_upload_default_public(
            session,
            tenant_context.tenant_id,
        ),
        s3_bucket=channel.bucket if channel.provider == "s3" else None,
        s3_endpoint_url=(channel.endpoint_url if channel.provider == "s3" else None),
        presigned_url_expire_seconds=(
            get_presigned_url_expire_seconds(
                session,
                tenant_context.tenant_id,
            )
            if channel.provider == "s3"
            else None
        ),
    )


@router.get(
    "/storage-channels",
    dependencies=[Depends(require_permission("system:file:channel:list"))],
    response_model=FileStorageChannelsPublic,
)
def read_storage_channels(
    session: SessionDep,
    tenant_context: CurrentTenant,
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    provider: str | None = None,
    is_active: bool | None = None,
) -> Any:
    page, page_size = normalize_pagination(page=page, page_size=page_size)
    filters = [FileStorageChannel.tenant_id == tenant_context.tenant_id]
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            or_(
                col(FileStorageChannel.name).ilike(pattern),
                col(FileStorageChannel.code).ilike(pattern),
                col(FileStorageChannel.bucket).ilike(pattern),
            )
        )
    if provider:
        filters.append(FileStorageChannel.provider == provider)
    if is_active is not None:
        filters.append(FileStorageChannel.is_active == is_active)

    count_statement = select(func.count()).select_from(FileStorageChannel)
    if filters:
        count_statement = count_statement.where(*filters)
    count = session.exec(count_statement).one()

    statement = select(FileStorageChannel)
    if filters:
        statement = statement.where(*filters)
    statement = (
        statement.order_by(
            col(FileStorageChannel.is_default).desc(),
            col(FileStorageChannel.created_at),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    channels = session.exec(statement).all()
    return FileStorageChannelsPublic(
        items=[mask_storage_channel(channel) for channel in channels],
        total=count,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/storage-channels",
    dependencies=[Depends(require_permission("system:file:channel:create"))],
    response_model=FileStorageChannelPublic,
)
def create_storage_channel(
    *,
    session: SessionDep,
    tenant_context: CurrentTenant,
    channel_in: FileStorageChannelCreate,
) -> Any:
    ensure_supported_provider(channel_in.provider)
    ensure_channel_code_unique(
        session=session,
        tenant_id=tenant_context.tenant_id,
        code=channel_in.code,
    )
    channel = FileStorageChannel.model_validate(
        channel_in,
        update={"tenant_id": tenant_context.tenant_id},
    )
    if channel.is_default:
        clear_default_storage_channels(
            session=session,
            tenant_id=tenant_context.tenant_id,
        )
    session.add(channel)
    session.commit()
    session.refresh(channel)
    return mask_storage_channel(channel)


@router.patch(
    "/storage-channels/{channel_id}",
    dependencies=[Depends(require_permission("system:file:channel:update"))],
    response_model=FileStorageChannelPublic,
)
def update_storage_channel(
    *,
    session: SessionDep,
    tenant_context: CurrentTenant,
    channel_id: uuid.UUID,
    channel_in: FileStorageChannelUpdate,
) -> Any:
    channel = session.exec(
        select(FileStorageChannel).where(
            FileStorageChannel.id == channel_id,
            FileStorageChannel.tenant_id == tenant_context.tenant_id,
        )
    ).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Storage channel not found")

    update_data = channel_in.model_dump(exclude_unset=True)
    if "provider" in update_data and update_data["provider"] is not None:
        ensure_supported_provider(update_data["provider"])
    if "code" in update_data and update_data["code"] != channel.code:
        ensure_channel_code_unique(
            session=session,
            tenant_id=tenant_context.tenant_id,
            code=update_data["code"],
            exclude_id=channel.id,
        )
    if update_data.get("is_default"):
        clear_default_storage_channels(
            session=session,
            tenant_id=tenant_context.tenant_id,
            exclude_id=channel.id,
        )

    channel.sqlmodel_update(update_data)
    channel.updated_at = get_datetime_utc()
    session.add(channel)
    session.commit()
    session.refresh(channel)
    return mask_storage_channel(channel)


@router.post(
    "/storage-channels/{channel_id}/test",
    dependencies=[Depends(require_permission("system:file:channel:update"))],
)
def test_storage_channel(
    session: SessionDep,
    tenant_context: CurrentTenant,
    channel_id: uuid.UUID,
) -> dict[str, str]:
    channel = session.exec(
        select(FileStorageChannel).where(
            FileStorageChannel.id == channel_id,
            FileStorageChannel.tenant_id == tenant_context.tenant_id,
        )
    ).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Storage channel not found")
    if channel.provider == "local":
        return {"message": "Storage channel is available"}
    if channel.provider != "s3":
        raise HTTPException(status_code=400, detail="Unsupported storage provider")
    client = _get_s3_client(channel)
    _ensure_s3_bucket(client, channel)
    return {"message": "Storage channel is available"}


@router.delete(
    "/storage-channels/{channel_id}",
    dependencies=[Depends(require_permission("system:file:channel:delete"))],
    status_code=204,
)
def delete_storage_channel(
    session: SessionDep,
    tenant_context: CurrentTenant,
    channel_id: uuid.UUID,
) -> None:
    channel = session.exec(
        select(FileStorageChannel).where(
            FileStorageChannel.id == channel_id,
            FileStorageChannel.tenant_id == tenant_context.tenant_id,
        )
    ).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Storage channel not found")
    if channel.is_default:
        raise HTTPException(
            status_code=400, detail="Cannot delete default storage channel"
        )
    session.delete(channel)
    session.commit()
    return None


@router.get(
    "/upload-config",
    dependencies=[Depends(require_permission("system:file:config:list"))],
    response_model=UploadConfigPublic,
)
def read_upload_config(
    session: SessionDep,
    tenant_context: CurrentTenant,
) -> UploadConfigPublic:
    return UploadConfigPublic(
        max_size_mb=get_upload_max_size_mb(session, tenant_context.tenant_id),
        allowed_extensions=get_upload_allowed_extensions(
            session,
            tenant_context.tenant_id,
        ),
        default_public=get_upload_default_public(
            session,
            tenant_context.tenant_id,
        ),
        presigned_url_expire_seconds=get_presigned_url_expire_seconds(
            session,
            tenant_context.tenant_id,
        ),
    )


@router.patch(
    "/upload-config",
    dependencies=[Depends(require_permission("system:file:config:update"))],
    response_model=UploadConfigPublic,
)
def update_upload_config(
    *,
    session: SessionDep,
    tenant_context: CurrentTenant,
    config_in: UploadConfigUpdate,
) -> UploadConfigPublic:
    update_data = config_in.model_dump(exclude_unset=True)
    setting_specs = {
        "max_size_mb": ("upload.max_size_mb", "上传大小限制 MB", "number"),
        "allowed_extensions": ("upload.allowed_extensions", "允许上传扩展名", "string"),
        "default_public": ("upload.default_public", "默认公开访问", "boolean"),
        "presigned_url_expire_seconds": (
            "upload.presigned_url_expire_seconds",
            "下载链接有效期秒数",
            "number",
        ),
    }
    for field, value in update_data.items():
        key, name, value_type = setting_specs[field]
        ensure_upload_setting(
            session=session,
            tenant_id=tenant_context.tenant_id,
            key=key,
            name=name,
            value=str(value).lower() if isinstance(value, bool) else str(value),
            value_type=value_type,
        )
    session.commit()
    return read_upload_config(session, tenant_context)


@router.get("/{file_id}", response_model=FileAssetPublic)
def read_file(
    session: SessionDep,
    current_user: CurrentUser,
    tenant_context: CurrentTenant,
    file_id: uuid.UUID,
) -> Any:
    file_asset = session.exec(
        select(FileAsset).where(
            FileAsset.id == file_id,
            FileAsset.tenant_id == tenant_context.tenant_id,
        )
    ).first()
    if not file_asset:
        raise HTTPException(status_code=404, detail="File not found")
    if not current_user.is_superuser and file_asset.uploader_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return file_asset


@router.get("/{file_id}/download-url", response_model=FileDownloadUrl)
def read_file_download_url(
    session: SessionDep,
    current_user: CurrentUser,
    tenant_context: CurrentTenant,
    file_id: uuid.UUID,
) -> FileDownloadUrl:
    file_asset = session.exec(
        select(FileAsset).where(
            FileAsset.id == file_id,
            FileAsset.tenant_id == tenant_context.tenant_id,
        )
    ).first()
    if not file_asset:
        raise HTTPException(status_code=404, detail="File not found")
    if (
        not file_asset.is_public
        and not current_user.is_superuser
        and file_asset.uploader_id != current_user.id
    ):
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return FileDownloadUrl(
        url=get_presigned_download_url(
            storage_provider=file_asset.storage_provider,
            storage_path=file_asset.storage_path,
            fallback_url=f"/api/v1/files/{file_asset.id}/download",
            session=session,
            tenant_id=tenant_context.tenant_id,
        ),
        expires_in=(
            get_presigned_url_expire_seconds(session, tenant_context.tenant_id)
            if file_asset.storage_provider == "s3"
            else None
        ),
    )


@router.get("/{file_id}/download")
def download_file(
    session: SessionDep,
    current_user: OptionalCurrentUser,
    request_tenant_id: OptionalTenantId,
    file_id: uuid.UUID,
) -> Any:
    file_asset = session.get(FileAsset, file_id)
    if not file_asset:
        raise HTTPException(status_code=404, detail="File not found")
    if current_user and request_tenant_id != file_asset.tenant_id:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    if not file_asset.is_public and (
        not current_user
        or (not current_user.is_superuser and file_asset.uploader_id != current_user.id)
    ):
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )

    return get_file_download_response(
        storage_provider=file_asset.storage_provider,
        storage_path=file_asset.storage_path,
        filename=file_asset.original_name,
        content_type=file_asset.content_type,
        session=session,
        tenant_id=file_asset.tenant_id,
    )


@router.delete(
    "/{file_id}",
    dependencies=[Depends(require_permission("system:file:delete"))],
    status_code=204,
)
def delete_file(
    session: SessionDep,
    tenant_context: CurrentTenant,
    file_id: uuid.UUID,
) -> None:
    file_asset = session.exec(
        select(FileAsset).where(
            FileAsset.id == file_id,
            FileAsset.tenant_id == tenant_context.tenant_id,
        )
    ).first()
    if not file_asset:
        raise HTTPException(status_code=404, detail="File not found")
    delete_stored_file(
        file_asset.storage_provider,
        file_asset.storage_path,
        session,
        file_asset.tenant_id,
    )
    session.delete(file_asset)
    session.commit()
    return None


@router.post("/avatar", response_model=UserPublic)
def upload_avatar(
    session: SessionDep,
    current_user: CurrentUser,
    tenant_context: CurrentTenant,
    file: UploadFile = File(...),
) -> Any:
    stored_file = save_upload_file(
        file,
        session=session,
        tenant_id=tenant_context.tenant_id,
    )
    try:
        ensure_file_quota(
            session=session,
            tenant_id=tenant_context.tenant_id,
            incoming_size=stored_file.size,
        )
    except HTTPException:
        delete_stored_file(
            stored_file.storage_provider,
            stored_file.storage_path,
            session,
            tenant_context.tenant_id,
        )
        raise
    if stored_file.extension not in {"gif", "jpeg", "jpg", "png", "webp"}:
        delete_stored_file(
            stored_file.storage_provider,
            stored_file.storage_path,
            session,
            tenant_context.tenant_id,
        )
        raise HTTPException(status_code=400, detail="Avatar must be an image")

    file_asset = FileAsset(
        tenant_id=tenant_context.tenant_id,
        original_name=stored_file.original_name,
        stored_name=stored_file.stored_name,
        content_type=stored_file.content_type,
        extension=stored_file.extension,
        size=stored_file.size,
        sha256=stored_file.sha256,
        storage_provider=stored_file.storage_provider,
        storage_path=stored_file.storage_path,
        uploader_id=current_user.id,
        is_public=True,
    )
    session.add(file_asset)
    session.commit()
    session.refresh(file_asset)
    file_asset.public_url = f"/api/v1/files/{file_asset.id}/download"
    current_user.avatar_url = file_asset.public_url
    current_user.updated_at = get_datetime_utc()
    session.add(file_asset)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user
