from fastapi.testclient import TestClient

from app.core.config import settings
from tests.utils.utils import random_lower_string


def test_superuser_can_read_seeded_menus(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/menus/me",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    menus = response.json()
    permission_codes = {menu["permission_code"] for menu in menus}
    assert "system:user:list" in permission_codes
    assert "system:role:list" in permission_codes
    assert "system:menu:list" in permission_codes


def test_superuser_can_read_permissions(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/permissions/me",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    permissions = set(response.json())
    assert "system:user:list" in permissions
    assert "system:role:update" in permissions
    assert "system:department:create" in permissions


def test_normal_user_cannot_read_roles(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/roles",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 403


def test_superuser_can_create_role_and_assign_menus(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    role_code = f"role_{random_lower_string()}"
    create_role_response = client.post(
        f"{settings.API_V1_STR}/roles",
        headers=superuser_token_headers,
        json={
            "code": role_code,
            "name": "测试角色",
            "description": "RBAC test role",
            "sort": 90,
            "is_active": True,
            "is_system": False,
        },
    )

    assert create_role_response.status_code == 200
    role = create_role_response.json()
    assert role["code"] == role_code

    menus_response = client.get(
        f"{settings.API_V1_STR}/menus",
        headers=superuser_token_headers,
    )
    assert menus_response.status_code == 200
    menu_ids = [
        menu["id"]
        for menu in menus_response.json()["items"]
        if menu["permission_code"] in {"system:user:list", "system:role:list"}
    ]
    assert len(menu_ids) == 2

    assign_response = client.put(
        f"{settings.API_V1_STR}/roles/{role['id']}/menus",
        headers=superuser_token_headers,
        json={"menu_ids": menu_ids},
    )
    assert assign_response.status_code == 200
    assert set(assign_response.json()) == set(menu_ids)

    read_response = client.get(
        f"{settings.API_V1_STR}/roles/{role['id']}/menus",
        headers=superuser_token_headers,
    )
    assert read_response.status_code == 200
    assert set(read_response.json()) == set(menu_ids)


def test_superuser_can_create_department(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    department_code = f"dept_{random_lower_string()}"
    response = client.post(
        f"{settings.API_V1_STR}/departments",
        headers=superuser_token_headers,
        json={
            "code": department_code,
            "name": "测试部门",
            "sort": 10,
            "is_active": True,
        },
    )

    assert response.status_code == 200
    department = response.json()
    assert department["code"] == department_code
    assert department["name"] == "测试部门"
