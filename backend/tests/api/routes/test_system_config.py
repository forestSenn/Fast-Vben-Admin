from fastapi.testclient import TestClient

from app.core.config import settings
from tests.utils.utils import random_lower_string


def test_superuser_can_read_seeded_dictionary_items(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/dictionaries/user_status/items",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    items = response.json()
    values = {item["value"] for item in items}
    assert {"active", "inactive"}.issubset(values)


def test_normal_user_cannot_manage_dictionary_types(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/dictionary-types",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 403


def test_superuser_can_create_dictionary_type_and_item(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    dictionary_code = f"dict_{random_lower_string()}"
    create_type_response = client.post(
        f"{settings.API_V1_STR}/dictionary-types",
        headers=superuser_token_headers,
        json={
            "code": dictionary_code,
            "name": "测试字典",
            "description": "Dictionary test",
            "is_active": True,
        },
    )

    assert create_type_response.status_code == 200
    dictionary_type = create_type_response.json()
    assert dictionary_type["code"] == dictionary_code

    create_item_response = client.post(
        f"{settings.API_V1_STR}/dictionary-items",
        headers=superuser_token_headers,
        json={
            "type_id": dictionary_type["id"],
            "label": "测试项",
            "value": "test",
            "color": "blue",
            "sort": 0,
            "is_active": True,
        },
    )
    assert create_item_response.status_code == 200
    item = create_item_response.json()
    assert item["value"] == "test"

    public_items_response = client.get(
        f"{settings.API_V1_STR}/dictionaries/{dictionary_code}/items",
        headers=superuser_token_headers,
    )
    assert public_items_response.status_code == 200
    assert public_items_response.json()[0]["label"] == "测试项"


def test_superuser_can_read_and_update_settings(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    list_response = client.get(
        f"{settings.API_V1_STR}/settings",
        headers=superuser_token_headers,
    )
    assert list_response.status_code == 200
    keys = {setting["key"] for setting in list_response.json()["items"]}
    assert "system.name" in keys

    update_response = client.patch(
        f"{settings.API_V1_STR}/settings/system.name",
        headers=superuser_token_headers,
        json={"value": "Fast Vben Admin Test"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["value"] == "Fast Vben Admin Test"


def test_public_settings_are_readable(client: TestClient) -> None:
    response = client.get(f"{settings.API_V1_STR}/settings/public")

    assert response.status_code == 200
    keys = {setting["key"] for setting in response.json()}
    assert "system.name" in keys
    assert "auth.allow_register" in keys
