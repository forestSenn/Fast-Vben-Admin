import hashlib
import shutil
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal, cast

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlmodel import Session, select

from app.core.config import settings
from app.core.tenancy import DEFAULT_TENANT_ID
from app.models import FileStorageChannel, SystemSetting

StorageProvider = Literal["local", "s3"]


@dataclass
class StoredFile:
    original_name: str
    stored_name: str
    content_type: str | None
    extension: str | None
    size: int
    sha256: str
    storage_path: str
    storage_provider: StorageProvider


def get_upload_setting(
    session: Session | None,
    key: str,
    default: str,
    tenant_id: uuid.UUID = DEFAULT_TENANT_ID,
) -> str:
    if session is None:
        return default
    setting = session.exec(
        select(SystemSetting).where(
            SystemSetting.tenant_id == tenant_id,
            SystemSetting.key == key,
        )
    ).first()
    return setting.value if setting else default


def get_upload_max_size_mb(
    session: Session | None = None,
    tenant_id: uuid.UUID = DEFAULT_TENANT_ID,
) -> int:
    value = get_upload_setting(
        session,
        "upload.max_size_mb",
        str(settings.UPLOAD_MAX_SIZE_MB),
        tenant_id,
    )
    try:
        return max(1, int(value))
    except ValueError:
        return settings.UPLOAD_MAX_SIZE_MB


def get_upload_allowed_extensions(
    session: Session | None = None,
    tenant_id: uuid.UUID = DEFAULT_TENANT_ID,
) -> str:
    return get_upload_setting(
        session,
        "upload.allowed_extensions",
        settings.UPLOAD_ALLOWED_EXTENSIONS,
        tenant_id,
    )


def get_upload_default_public(
    session: Session | None = None,
    tenant_id: uuid.UUID = DEFAULT_TENANT_ID,
) -> bool:
    value = get_upload_setting(
        session,
        "upload.default_public",
        "false",
        tenant_id,
    )
    return value.lower() in {"1", "true", "yes"}


def get_presigned_url_expire_seconds(
    session: Session | None = None,
    tenant_id: uuid.UUID = DEFAULT_TENANT_ID,
) -> int:
    value = get_upload_setting(
        session,
        "upload.presigned_url_expire_seconds",
        str(settings.S3_PRESIGNED_URL_EXPIRE_SECONDS),
        tenant_id,
    )
    try:
        return max(60, int(value))
    except ValueError:
        return settings.S3_PRESIGNED_URL_EXPIRE_SECONDS


def get_default_storage_channel(
    session: Session | None = None,
    tenant_id: uuid.UUID = DEFAULT_TENANT_ID,
) -> FileStorageChannel:
    if session is not None:
        channel = session.exec(
            select(FileStorageChannel)
            .where(
                FileStorageChannel.tenant_id == tenant_id,
                FileStorageChannel.is_active,
                FileStorageChannel.is_default,
            )
            .order_by(FileStorageChannel.created_at)
        ).first()
        if channel:
            return channel

    return FileStorageChannel(
        tenant_id=tenant_id,
        name="本地存储" if settings.STORAGE_PROVIDER == "local" else "默认对象存储",
        code="local" if settings.STORAGE_PROVIDER == "local" else "default-s3",
        provider=settings.STORAGE_PROVIDER,
        endpoint_url=settings.S3_ENDPOINT_URL,
        region=settings.S3_REGION,
        bucket=settings.S3_BUCKET,
        access_key_id=settings.S3_ACCESS_KEY_ID,
        secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        object_prefix=settings.S3_OBJECT_PREFIX,
        addressing_style=settings.S3_ADDRESSING_STYLE,
        auto_create_bucket=settings.S3_AUTO_CREATE_BUCKET,
        is_default=True,
        is_active=True,
    )


def get_upload_root() -> Path:
    upload_root = Path(settings.UPLOAD_DIR)
    if not upload_root.is_absolute():
        upload_root = Path(__file__).resolve().parents[1] / upload_root
    upload_root.mkdir(parents=True, exist_ok=True)
    return upload_root


def get_allowed_extensions(
    session: Session | None = None,
    tenant_id: uuid.UUID = DEFAULT_TENANT_ID,
) -> set[str]:
    return {
        extension.strip().lower().lstrip(".")
        for extension in get_upload_allowed_extensions(session, tenant_id).split(",")
        if extension.strip()
    }


def get_extension(filename: str) -> str | None:
    suffix = Path(filename).suffix.lower().lstrip(".")
    return suffix or None


def validate_upload(
    file: UploadFile,
    session: Session | None = None,
    tenant_id: uuid.UUID = DEFAULT_TENANT_ID,
) -> str | None:
    extension = get_extension(file.filename or "")
    allowed_extensions = get_allowed_extensions(session, tenant_id)
    if allowed_extensions and (not extension or extension not in allowed_extensions):
        raise HTTPException(status_code=400, detail="File extension is not allowed")
    return extension


def _build_storage_path(
    stored_name: str,
    channel: FileStorageChannel,
    tenant_id: uuid.UUID,
) -> str:
    now = datetime.now(UTC)
    relative_path = (
        Path("tenants")
        / str(tenant_id)
        / str(now.year)
        / f"{now.month:02d}"
        / stored_name
    )
    if channel.provider == "s3":
        prefix = (channel.object_prefix or "").strip("/")
        if prefix:
            relative_path = Path(prefix) / relative_path
    return str(relative_path).replace("\\", "/")


def _save_to_temporary_file(
    file: UploadFile,
    session: Session | None = None,
    tenant_id: uuid.UUID = DEFAULT_TENANT_ID,
) -> tuple[Path, int, str]:
    max_size = get_upload_max_size_mb(session, tenant_id) * 1024 * 1024
    digest = hashlib.sha256()
    size = 0
    temporary_file = NamedTemporaryFile(delete=False)
    temporary_path = Path(temporary_file.name)
    try:
        with temporary_file:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > max_size:
                    raise HTTPException(status_code=400, detail="File is too large")
                digest.update(chunk)
                temporary_file.write(chunk)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return temporary_path, size, digest.hexdigest()


def _get_s3_client(channel: FileStorageChannel | None = None) -> Any:
    channel = channel or get_default_storage_channel()
    if not channel.bucket:
        raise HTTPException(status_code=503, detail="S3_BUCKET is not configured")

    config = None
    if channel.addressing_style != "auto":
        config = Config(s3={"addressing_style": channel.addressing_style})
    return boto3.client(
        "s3",
        aws_access_key_id=channel.access_key_id,
        aws_secret_access_key=channel.secret_access_key,
        endpoint_url=channel.endpoint_url,
        region_name=channel.region or settings.S3_REGION,
        config=config,
    )


def _ensure_s3_bucket(client: Any, channel: FileStorageChannel) -> None:
    if not channel.bucket:
        raise HTTPException(status_code=503, detail="S3_BUCKET is not configured")
    try:
        client.head_bucket(Bucket=channel.bucket)
        return
    except ClientError:
        if not channel.auto_create_bucket:
            raise HTTPException(status_code=503, detail="S3 bucket is not available")
    try:
        create_kwargs: dict[str, object] = {"Bucket": channel.bucket}
        region = channel.region or settings.S3_REGION
        if region != "us-east-1":
            create_kwargs["CreateBucketConfiguration"] = {"LocationConstraint": region}
        client.create_bucket(**create_kwargs)
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=503, detail="Unable to create S3 bucket"
        ) from exc


def save_upload_file(
    file: UploadFile,
    session: Session | None = None,
    tenant_id: uuid.UUID = DEFAULT_TENANT_ID,
) -> StoredFile:
    channel = get_default_storage_channel(session, tenant_id)
    extension = validate_upload(file, session, tenant_id)
    stored_name = f"{uuid.uuid4().hex}{f'.{extension}' if extension else ''}"
    storage_path = _build_storage_path(stored_name, channel, tenant_id)
    temporary_path, size, sha256 = _save_to_temporary_file(
        file,
        session,
        tenant_id,
    )

    try:
        if channel.provider == "local":
            destination = get_local_file_path(storage_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(temporary_path), destination)
        else:
            client = _get_s3_client(channel)
            _ensure_s3_bucket(client, channel)
            extra_args: dict[str, str] = {}
            if file.content_type:
                extra_args["ContentType"] = file.content_type
            with temporary_path.open("rb") as source:
                client.upload_fileobj(
                    source,
                    channel.bucket,
                    storage_path,
                    ExtraArgs=extra_args or None,
                )
    except HTTPException:
        raise
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(status_code=503, detail="Unable to store file") from exc
    finally:
        temporary_path.unlink(missing_ok=True)

    return StoredFile(
        original_name=file.filename or stored_name,
        stored_name=stored_name,
        content_type=file.content_type,
        extension=extension,
        size=size,
        sha256=sha256,
        storage_path=storage_path,
        storage_provider=cast(StorageProvider, channel.provider),
    )


def get_local_file_path(storage_path: str) -> Path:
    upload_root = get_upload_root().resolve()
    file_path = (upload_root / storage_path).resolve()
    if upload_root not in file_path.parents and file_path != upload_root:
        raise HTTPException(status_code=400, detail="Invalid file path")
    return file_path


def delete_stored_file(
    storage_provider: str,
    storage_path: str,
    session: Session | None = None,
    tenant_id: uuid.UUID = DEFAULT_TENANT_ID,
) -> None:
    if storage_provider == "local":
        get_local_file_path(storage_path).unlink(missing_ok=True)
        return
    if storage_provider != "s3":
        raise HTTPException(status_code=400, detail="Unsupported storage provider")
    channel = get_default_storage_channel(session, tenant_id)
    try:
        _get_s3_client(channel).delete_object(Bucket=channel.bucket, Key=storage_path)
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=503, detail="Unable to delete stored file"
        ) from exc


def delete_local_file(storage_path: str) -> None:
    """Compatibility helper for existing internal callers."""
    delete_stored_file("local", storage_path)


def _stream_s3_object(
    storage_path: str,
    session: Session | None = None,
    tenant_id: uuid.UUID = DEFAULT_TENANT_ID,
) -> Iterator[bytes]:
    channel = get_default_storage_channel(session, tenant_id)
    try:
        response = _get_s3_client(channel).get_object(
            Bucket=channel.bucket, Key=storage_path
        )
        body = response["Body"]
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(status_code=404, detail="File content not found") from exc
    try:
        while chunk := body.read(1024 * 1024):
            yield chunk
    finally:
        body.close()


def get_file_download_response(
    *,
    storage_provider: str,
    storage_path: str,
    filename: str,
    content_type: str | None,
    session: Session | None = None,
    tenant_id: uuid.UUID = DEFAULT_TENANT_ID,
) -> FileResponse | StreamingResponse:
    if storage_provider == "local":
        file_path = get_local_file_path(storage_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File content not found")
        return FileResponse(file_path, filename=filename, media_type=content_type)
    if storage_provider != "s3":
        raise HTTPException(status_code=400, detail="Unsupported storage provider")
    return StreamingResponse(
        _stream_s3_object(storage_path, session, tenant_id),
        media_type=content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def get_presigned_download_url(
    *,
    storage_provider: str,
    storage_path: str,
    fallback_url: str,
    session: Session | None = None,
    tenant_id: uuid.UUID = DEFAULT_TENANT_ID,
) -> str:
    if storage_provider == "local":
        return fallback_url
    if storage_provider != "s3":
        raise HTTPException(status_code=400, detail="Unsupported storage provider")
    channel = get_default_storage_channel(session, tenant_id)
    try:
        return _get_s3_client(channel).generate_presigned_url(
            "get_object",
            Params={"Bucket": channel.bucket, "Key": storage_path},
            ExpiresIn=get_presigned_url_expire_seconds(session, tenant_id),
        )
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=503, detail="Unable to create a download URL"
        ) from exc


def copy_file_to_uploads(source: Path, filename: str) -> StoredFile:
    # Test helper and future internal import utility.
    class LocalUpload:
        def __init__(self, path: Path, name: str) -> None:
            self.filename = name
            self.content_type = None
            self.file = path.open("rb")

    upload = LocalUpload(source, filename)
    try:
        return save_upload_file(cast(UploadFile, upload))
    finally:
        upload.file.close()
