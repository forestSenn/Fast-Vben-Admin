import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.core.config import settings


@dataclass
class StoredFile:
    original_name: str
    stored_name: str
    content_type: str | None
    extension: str | None
    size: int
    sha256: str
    storage_path: str


def get_upload_root() -> Path:
    upload_root = Path(settings.UPLOAD_DIR)
    if not upload_root.is_absolute():
        upload_root = Path(__file__).resolve().parents[1] / upload_root
    upload_root.mkdir(parents=True, exist_ok=True)
    return upload_root


def get_allowed_extensions() -> set[str]:
    return {
        extension.strip().lower().lstrip(".")
        for extension in settings.UPLOAD_ALLOWED_EXTENSIONS.split(",")
        if extension.strip()
    }


def get_extension(filename: str) -> str | None:
    suffix = Path(filename).suffix.lower().lstrip(".")
    return suffix or None


def validate_upload(file: UploadFile) -> str | None:
    extension = get_extension(file.filename or "")
    allowed_extensions = get_allowed_extensions()
    if allowed_extensions and (not extension or extension not in allowed_extensions):
        raise HTTPException(status_code=400, detail="File extension is not allowed")
    return extension


def save_upload_file(file: UploadFile) -> StoredFile:
    extension = validate_upload(file)
    now = datetime.now(UTC)
    relative_dir = Path(str(now.year)) / f"{now.month:02d}"
    upload_dir = get_upload_root() / relative_dir
    upload_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid.uuid4().hex}{f'.{extension}' if extension else ''}"
    destination = upload_dir / stored_name
    max_size = settings.UPLOAD_MAX_SIZE_MB * 1024 * 1024
    digest = hashlib.sha256()
    size = 0

    with destination.open("wb") as output:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > max_size:
                output.close()
                destination.unlink(missing_ok=True)
                raise HTTPException(status_code=400, detail="File is too large")
            digest.update(chunk)
            output.write(chunk)

    storage_path = str(relative_dir / stored_name).replace("\\", "/")
    return StoredFile(
        original_name=file.filename or stored_name,
        stored_name=stored_name,
        content_type=file.content_type,
        extension=extension,
        size=size,
        sha256=digest.hexdigest(),
        storage_path=storage_path,
    )


def get_local_file_path(storage_path: str) -> Path:
    upload_root = get_upload_root().resolve()
    file_path = (upload_root / storage_path).resolve()
    if upload_root not in file_path.parents and file_path != upload_root:
        raise HTTPException(status_code=400, detail="Invalid file path")
    return file_path


def delete_local_file(storage_path: str) -> None:
    file_path = get_local_file_path(storage_path)
    file_path.unlink(missing_ok=True)


def copy_file_to_uploads(source: Path, filename: str) -> StoredFile:
    # Test helper and future internal import utility.
    class LocalUpload:
        def __init__(self, path: Path, name: str) -> None:
            self.filename = name
            self.content_type = None
            self.file = path.open("rb")

    upload = LocalUpload(source, filename)
    try:
        return save_upload_file(upload)  # type: ignore[arg-type]
    finally:
        upload.file.close()
