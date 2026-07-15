from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import User
from tests.utils.utils import random_lower_string


def test_manage_site_message_template_and_send(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    suffix = random_lower_string()[:8]
    user = db.exec(select(User).where(User.email == settings.EMAIL_TEST_USER)).first()
    assert user

    template_response = client.post(
        f"{settings.API_V1_STR}/site-messages/templates",
        headers=superuser_token_headers,
        json={
            "name": f"任务提醒 {suffix}",
            "code": f"task-{suffix}",
            "sender_name": "工作流程",
            "content": "您好，{name}，您收到任务 {task}。",
            "type": "task",
            "is_active": True,
        },
    )
    assert template_response.status_code == 200
    template = template_response.json()
    assert template["params"] == "name,task"

    missing_param_response = client.post(
        f"{settings.API_V1_STR}/site-messages/templates/{template['id']}/send-test",
        headers=superuser_token_headers,
        json={
            "user_id": str(user.id),
            "template_params": {"name": "Alice"},
        },
    )
    assert missing_param_response.status_code == 400

    send_response = client.post(
        f"{settings.API_V1_STR}/site-messages/templates/{template['id']}/send-test",
        headers=superuser_token_headers,
        json={
            "user_id": str(user.id),
            "template_params": {"name": "Alice", "task": "审批"},
        },
    )
    assert send_response.status_code == 200
    site_message = send_response.json()
    assert site_message["template_code"] == template["code"]
    assert site_message["sender_name"] == "工作流程"
    assert site_message["content"] == "您好，Alice，您收到任务 审批。"
    assert site_message["is_read"] is False

    admin_list_response = client.get(
        f"{settings.API_V1_STR}/site-messages/messages",
        headers=superuser_token_headers,
        params={"template_code": template["code"]},
    )
    assert admin_list_response.status_code == 200
    assert any(
        item["id"] == site_message["id"] for item in admin_list_response.json()["items"]
    )

    my_messages_response = client.get(
        f"{settings.API_V1_STR}/messages/me",
        headers=normal_user_token_headers,
        params={"is_read": False},
    )
    assert my_messages_response.status_code == 200
    assert any(
        item["id"] == site_message["id"]
        for item in my_messages_response.json()["items"]
    )

    delete_message_response = client.delete(
        f"{settings.API_V1_STR}/site-messages/messages/{site_message['id']}",
        headers=superuser_token_headers,
    )
    assert delete_message_response.status_code == 204
    delete_template_response = client.delete(
        f"{settings.API_V1_STR}/site-messages/templates/{template['id']}",
        headers=superuser_token_headers,
    )
    assert delete_template_response.status_code == 204


def test_normal_user_cannot_access_site_message_management(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/site-messages/templates",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
