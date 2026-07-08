import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import col, func, or_, select

from app.api.deps import CurrentUser, SessionDep, require_permission
from app.models import (
    FileAsset,
    FileAssetPublic,
    FileAssetsPublic,
    UserPublic,
    get_datetime_utc,
)
from app.storage import delete_local_file, get_local_file_path, save_upload_file

router = APIRouter(prefix="/files", tags=["files"])


@router.get(
    "",
    dependencies=[Depends(require_permission("system:file:list"))],
    response_model=FileAssetsPublic,
)
def read_files(
    session: SessionDep,
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
) -> Any:
    filters = []
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            or_(
                col(FileAsset.original_name).ilike(pattern),
                col(FileAsset.content_type).ilike(pattern),
                col(FileAsset.extension).ilike(pattern),
            )
        )

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


@router.post("/upload", response_model=FileAssetPublic)
def upload_file(
    session: SessionDep,
    current_user: CurrentUser,
    file: UploadFile = File(...),
    is_public: bool = False,
) -> Any:
    stored_file = save_upload_file(file)
    file_asset = FileAsset(
        original_name=stored_file.original_name,
        stored_name=stored_file.stored_name,
        content_type=stored_file.content_type,
        extension=stored_file.extension,
        size=stored_file.size,
        sha256=stored_file.sha256,
        storage_provider="local",
        storage_path=stored_file.storage_path,
        public_url=None,
        uploader_id=current_user.id,
        is_public=is_public,
    )
    session.add(file_asset)
    session.commit()
    session.refresh(file_asset)
    file_asset.public_url = f"/api/v1/files/{file_asset.id}/download"
    session.add(file_asset)
    session.commit()
    session.refresh(file_asset)
    return file_asset


@router.get("/{file_id}", response_model=FileAssetPublic)
def read_file(session: SessionDep, current_user: CurrentUser, file_id: uuid.UUID) -> Any:
    file_asset = session.get(FileAsset, file_id)
    if not file_asset:
        raise HTTPException(status_code=404, detail="File not found")
    if not current_user.is_superuser and file_asset.uploader_id != current_user.id:
        raise HTTPException(status_code=403, detail="The user doesn't have enough privileges")
    return file_asset


@router.get("/{file_id}/download")
def download_file(
    session: SessionDep,
    current_user: CurrentUser,
    file_id: uuid.UUID,
) -> FileResponse:
    file_asset = session.get(FileAsset, file_id)
    if not file_asset:
        raise HTTPException(status_code=404, detail="File not found")
    if not file_asset.is_public and not current_user.is_superuser and file_asset.uploader_id != current_user.id:
        raise HTTPException(status_code=403, detail="The user doesn't have enough privileges")

    file_path = get_local_file_path(file_asset.storage_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File content not found")
    return FileResponse(
        file_path,
        filename=file_asset.original_name,
        media_type=file_asset.content_type,
    )


@router.delete(
    "/{file_id}",
    dependencies=[Depends(require_permission("system:file:delete"))],
    status_code=204,
)
def delete_file(session: SessionDep, file_id: uuid.UUID) -> None:
    file_asset = session.get(FileAsset, file_id)
    if not file_asset:
        raise HTTPException(status_code=404, detail="File not found")
    delete_local_file(file_asset.storage_path)
    session.delete(file_asset)
    session.commit()
    return None


@router.post("/avatar", response_model=UserPublic)
def upload_avatar(
    session: SessionDep,
    current_user: CurrentUser,
    file: UploadFile = File(...),
) -> Any:
    stored_file = save_upload_file(file)
    if stored_file.extension not in {"gif", "jpeg", "jpg", "png", "webp"}:
        delete_local_file(stored_file.storage_path)
        raise HTTPException(status_code=400, detail="Avatar must be an image")

    file_asset = FileAsset(
        original_name=stored_file.original_name,
        stored_name=stored_file.stored_name,
        content_type=stored_file.content_type,
        extension=stored_file.extension,
        size=stored_file.size,
        sha256=stored_file.sha256,
        storage_provider="local",
        storage_path=stored_file.storage_path,
        uploader_id=current_user.id,
        is_public=False,
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
