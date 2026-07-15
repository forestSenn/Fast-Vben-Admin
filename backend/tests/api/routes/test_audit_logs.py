from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.core.config import settings
from tests.utils.utils import random_lower_string


def test_login_success_and_failure_are_logged(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    failed_login = client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": settings.FIRST_SUPERUSER, "password": "wrong-password"},
    )
    assert failed_login.status_code == 401

    successful_login = client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={
            "username": settings.FIRST_SUPERUSER,
            "password": settings.FIRST_SUPERUSER_PASSWORD,
        },
    )
    assert successful_login.status_code == 200

    logs_response = client.get(
        f"{settings.API_V1_STR}/logs/login",
        headers=superuser_token_headers,
        params={"keyword": settings.FIRST_SUPERUSER, "page_size": 50},
    )
    assert logs_response.status_code == 200
    statuses = {log["status"] for log in logs_response.json()["items"]}
    assert {"fail", "success"}.issubset(statuses)

    filtered_response = client.get(
        f"{settings.API_V1_STR}/logs/login",
        headers=superuser_token_headers,
        params={
            "created_from": (datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
            "created_to": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
            "keyword": settings.FIRST_SUPERUSER,
        },
    )
    assert filtered_response.status_code == 200
    assert filtered_response.json()["total"] >= 1


def test_operation_log_is_written_for_mutating_request(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    role_code = f"audit_{random_lower_string()}"
    create_response = client.post(
        f"{settings.API_V1_STR}/roles",
        headers=superuser_token_headers,
        json={
            "code": role_code,
            "name": f"审计测试角色_{role_code}",
            "description": "operation log test",
            "sort": 99,
            "is_active": True,
            "is_system": False,
        },
    )
    assert create_response.status_code == 200
    role = create_response.json()

    try:
        logs_response = client.get(
            f"{settings.API_V1_STR}/logs/operation",
            headers=superuser_token_headers,
            params={"keyword": "/api/v1/roles", "method": "POST", "page_size": 50},
        )
        assert logs_response.status_code == 200
        logs = logs_response.json()["items"]
        assert any(
            log["path"] == f"{settings.API_V1_STR}/roles"
            and log["method"] == "POST"
            and log["status_code"] == 200
            for log in logs
        )

        filtered_response = client.get(
            f"{settings.API_V1_STR}/logs/operation",
            headers=superuser_token_headers,
            params={
                "created_from": (datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
                "created_to": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
                "keyword": "/api/v1/roles",
            },
        )
        assert filtered_response.status_code == 200
        assert filtered_response.json()["total"] >= 1
    finally:
        delete_response = client.delete(
            f"{settings.API_V1_STR}/roles/{role['id']}",
            headers=superuser_token_headers,
        )
        assert delete_response.status_code == 204


def test_normal_user_cannot_read_audit_logs(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    login_logs_response = client.get(
        f"{settings.API_V1_STR}/logs/login",
        headers=normal_user_token_headers,
    )
    operation_logs_response = client.get(
        f"{settings.API_V1_STR}/logs/operation",
        headers=normal_user_token_headers,
    )

    assert login_logs_response.status_code == 403
    assert operation_logs_response.status_code == 403
