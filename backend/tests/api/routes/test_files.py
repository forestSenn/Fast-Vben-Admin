from io import BytesIO

from fastapi.testclient import TestClient

from app.core.config import settings


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


def test_normal_user_cannot_list_files(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/files",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 403
