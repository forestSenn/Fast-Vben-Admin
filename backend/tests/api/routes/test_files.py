from collections.abc import Generator
from io import BytesIO
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import FileAsset, FileStorageChannel, SystemSetting, User
from app.storage import delete_stored_file


@pytest.fixture(autouse=True)
def reset_file_storage_state(db: Session) -> Generator[None]:
    db.rollback()
    original_file_asset_ids = {
        file_asset.id for file_asset in db.exec(select(FileAsset)).all()
    }
    original_avatar_urls = {
        user.id: user.avatar_url for user in db.exec(select(User)).all()
    }
    local_channel = None
    for channel in db.exec(select(FileStorageChannel)).all():
        if channel.code in {"s3-test", "minio-test"}:
            db.delete(channel)
        elif channel.code == "local":
            local_channel = channel
            channel.name = "本地存储"
            channel.provider = "local"
            channel.is_default = True
            channel.is_active = True
            db.add(channel)
        else:
            channel.is_default = False
            db.add(channel)
    if local_channel is None:
        db.add(
            FileStorageChannel(
                name="本地存储",
                code="local",
                provider="local",
                is_default=True,
                is_active=True,
            )
        )
    for key, (value, value_type) in {
        "upload.max_size_mb": ("10", "number"),
        "upload.allowed_extensions": (settings.UPLOAD_ALLOWED_EXTENSIONS, "string"),
        "upload.default_public": ("false", "boolean"),
        "upload.presigned_url_expire_seconds": (
            str(settings.S3_PRESIGNED_URL_EXPIRE_SECONDS),
            "number",
        ),
    }.items():
        setting = db.exec(select(SystemSetting).where(SystemSetting.key == key)).first()
        if setting:
            setting.value = value
            setting.value_type = value_type
            db.add(setting)
    db.commit()
    yield
    db.rollback()
    for user in db.exec(select(User)).all():
        if user.id in original_avatar_urls:
            user.avatar_url = original_avatar_urls[user.id]
            db.add(user)
    for file_asset in db.exec(select(FileAsset)).all():
        if file_asset.id not in original_file_asset_ids:
            if file_asset.storage_provider == "local":
                delete_stored_file(
                    file_asset.storage_provider,
                    file_asset.storage_path,
                    db,
                )
            db.delete(file_asset)
    local_channel = None
    for channel in db.exec(select(FileStorageChannel)).all():
        if channel.code in {"s3-test", "minio-test"}:
            db.delete(channel)
        elif channel.code == "local":
            local_channel = channel
            channel.is_default = True
            channel.is_active = True
            db.add(channel)
        else:
            channel.is_default = False
            db.add(channel)
    if local_channel is None:
        db.add(
            FileStorageChannel(
                name="本地存储",
                code="local",
                provider="local",
                is_default=True,
                is_active=True,
            )
        )
    db.commit()


def test_upload_list_and_download_file(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    upload_response = client.post(
        f"{settings.API_V1_STR}/files/upload",
        headers=superuser_token_headers,
        files={"file": ("hello.txt", BytesIO(b"hello"), "text/plain")},
    )

    assert upload_response.status_code == 200
    file_asset = upload_response.json()
    assert file_asset["original_name"] == "hello.txt"
    assert file_asset["size"] == 5
    assert file_asset["public_url"]

    list_response = client.get(
        f"{settings.API_V1_STR}/files",
        headers=superuser_token_headers,
        params={"keyword": "hello.txt"},
    )
    assert list_response.status_code == 200
    assert any(item["id"] == file_asset["id"] for item in list_response.json()["items"])

    download_response = client.get(
        f"{settings.API_V1_STR}/files/{file_asset['id']}/download",
        headers=superuser_token_headers,
    )
    assert download_response.status_code == 200
    assert download_response.content == b"hello"


def test_upload_rejects_disallowed_extension(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/files/upload",
        headers=superuser_token_headers,
        files={"file": ("malware.exe", BytesIO(b"nope"), "application/octet-stream")},
    )

    assert response.status_code == 400


def test_avatar_upload_updates_current_user(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/files/avatar",
        headers=superuser_token_headers,
        files={"file": ("avatar.png", BytesIO(b"fake-png"), "image/png")},
    )

    assert response.status_code == 200
    user = response.json()
    assert user["avatar_url"]
    avatar_response = client.get(user["avatar_url"])
    assert avatar_response.status_code == 200


def test_normal_user_cannot_list_files(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/files",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 403


def test_read_storage_config(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/files/storage-config",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    assert response.json()["provider"] == "local"
    assert response.json()["channel_name"]
    assert response.json()["max_size_mb"] >= 1


def test_manage_storage_channels(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    create_response = client.post(
        f"{settings.API_V1_STR}/files/storage-channels",
        headers=superuser_token_headers,
        json={
            "name": "MinIO 测试",
            "code": "minio-test",
            "provider": "s3",
            "endpoint_url": "http://localhost:9000",
            "region": "us-east-1",
            "bucket": "uploads",
            "access_key_id": "minio",
            "secret_access_key": "secret",
            "object_prefix": "files",
            "addressing_style": "path",
            "auto_create_bucket": True,
            "is_default": False,
            "is_active": True,
        },
    )
    assert create_response.status_code == 200
    channel = create_response.json()
    assert channel["secret_access_key"] == "******"

    list_response = client.get(
        f"{settings.API_V1_STR}/files/storage-channels",
        headers=superuser_token_headers,
        params={"keyword": "minio-test"},
    )
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    update_response = client.patch(
        f"{settings.API_V1_STR}/files/storage-channels/{channel['id']}",
        headers=superuser_token_headers,
        json={"is_active": False},
    )
    assert update_response.status_code == 200
    assert update_response.json()["is_active"] is False

    delete_response = client.delete(
        f"{settings.API_V1_STR}/files/storage-channels/{channel['id']}",
        headers=superuser_token_headers,
    )
    assert delete_response.status_code == 204


def test_update_upload_config(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.patch(
        f"{settings.API_V1_STR}/files/upload-config",
        headers=superuser_token_headers,
        json={
            "max_size_mb": 20,
            "allowed_extensions": "txt,pdf",
            "default_public": True,
            "presigned_url_expire_seconds": 600,
        },
    )
    assert response.status_code == 200
    config = response.json()
    assert config["max_size_mb"] == 20
    assert config["allowed_extensions"] == "txt,pdf"
    assert config["default_public"] is True
    assert config["presigned_url_expire_seconds"] == 600


def test_normal_user_cannot_upload_managed_file(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/files/upload",
        headers=normal_user_token_headers,
        files={"file": ("hello.txt", BytesIO(b"hello"), "text/plain")},
    )

    assert response.status_code == 403


def test_s3_storage_upload_download_and_presigned_url(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    class FakeS3Client:
        def __init__(self) -> None:
            self.objects: dict[str, bytes] = {}

        def head_bucket(self, **_kwargs: object) -> None:
            return None

        def upload_fileobj(
            self,
            source: object,
            _bucket: str,
            key: str,
            ExtraArgs: object = None,  # noqa: N803
        ) -> None:
            del ExtraArgs
            self.objects[key] = source.read()  # type: ignore[union-attr]

        def get_object(self, *, Bucket: str, Key: str) -> dict[str, BytesIO]:  # noqa: N803
            del Bucket
            return {"Body": BytesIO(self.objects[Key])}

        def generate_presigned_url(self, *_args: object, **_kwargs: object) -> str:
            return "https://storage.example.test/signed-download"

        def delete_object(self, *, Bucket: str, Key: str) -> None:  # noqa: N803
            del Bucket
            self.objects.pop(Key, None)

    fake_s3 = FakeS3Client()
    channel = FileStorageChannel(
        name="S3",
        code="s3-test",
        provider="s3",
        bucket="test-bucket",
        is_default=True,
        is_active=True,
    )
    for existing in db.exec(select(FileStorageChannel)).all():
        existing.is_default = False
        db.add(existing)
    db.add(channel)
    db.commit()

    with (
        patch("app.storage._get_s3_client", return_value=fake_s3),
    ):
        upload_response = client.post(
            f"{settings.API_V1_STR}/files/upload",
            headers=superuser_token_headers,
            files={"file": ("stored.txt", BytesIO(b"stored"), "text/plain")},
        )
        assert upload_response.status_code == 200
        file_asset = upload_response.json()
        assert file_asset["storage_provider"] == "s3"

        download_response = client.get(
            f"{settings.API_V1_STR}/files/{file_asset['id']}/download",
            headers=superuser_token_headers,
        )
        assert download_response.status_code == 200
        assert download_response.content == b"stored"

        url_response = client.get(
            f"{settings.API_V1_STR}/files/{file_asset['id']}/download-url",
            headers=superuser_token_headers,
        )
        assert url_response.status_code == 200
        assert (
            url_response.json()["url"] == "https://storage.example.test/signed-download"
        )
