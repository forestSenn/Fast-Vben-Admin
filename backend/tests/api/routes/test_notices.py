from fastapi.testclient import TestClient

from app.core.config import settings


def test_notice_publish_creates_my_message(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    create_response = client.post(
        f"{settings.API_V1_STR}/notices",
        headers=superuser_token_headers,
        json={
            "title": "维护通知",
            "content": "今晚发布新版本",
            "type": "notice",
            "priority": 1,
        },
    )
    assert create_response.status_code == 200
    notice = create_response.json()
    assert notice["status"] == "draft"

    publish_response = client.post(
        f"{settings.API_V1_STR}/notices/{notice['id']}/publish",
        headers=superuser_token_headers,
    )
    assert publish_response.status_code == 200
    assert publish_response.json()["status"] == "published"

    current_response = client.get(
        f"{settings.API_V1_STR}/notices/current",
        headers=superuser_token_headers,
    )
    assert current_response.status_code == 200
    assert any(item["id"] == notice["id"] for item in current_response.json())

    messages_response = client.get(
        f"{settings.API_V1_STR}/messages/me",
        headers=superuser_token_headers,
    )
    assert messages_response.status_code == 200
    messages = messages_response.json()["items"]
    message = next(item for item in messages if item["notice_id"] == notice["id"])
    assert message["is_read"] is False

    read_response = client.post(
        f"{settings.API_V1_STR}/messages/{message['id']}/read",
        headers=superuser_token_headers,
    )
    assert read_response.status_code == 200
    assert read_response.json()["is_read"] is True


def test_normal_user_cannot_manage_notices(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/notices",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 403
