from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, delete, select

from app.core.cache import CacheNamespace, redis_cache
from app.core.config import settings
from app.core.tenancy import DEFAULT_TENANT_ID
from app.models import (
    DictionaryItem,
    DictionaryType,
    Role,
    SystemSetting,
    Tenant,
    TenantMembership,
    UserPost,
    UserRole,
    UserSession,
)
from tests.utils.utils import get_superuser_token_headers, random_lower_string


def _delete_dictionary_type(
    client: TestClient,
    headers: dict[str, str],
    type_id: str,
    item_id: str | None = None,
) -> None:
    if item_id:
        client.delete(
            f"{settings.API_V1_STR}/dictionary-items/{item_id}",
            headers=headers,
        )
    client.delete(
        f"{settings.API_V1_STR}/dictionary-types/{type_id}",
        headers=headers,
    )


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
    type_id: str | None = None
    item_id: str | None = None
    try:
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
        type_id = dictionary_type["id"]
        assert dictionary_type["code"] == dictionary_code

        create_item_response = client.post(
            f"{settings.API_V1_STR}/dictionary-items",
            headers=superuser_token_headers,
            json={
                "type_id": type_id,
                "label": "测试项",
                "value": "test",
                "color": "blue",
                "sort": 0,
                "is_active": True,
            },
        )
        assert create_item_response.status_code == 200
        item = create_item_response.json()
        item_id = item["id"]
        assert item["value"] == "test"

        public_items_response = client.get(
            f"{settings.API_V1_STR}/dictionaries/{dictionary_code}/items",
            headers=superuser_token_headers,
        )
        assert public_items_response.status_code == 200
        assert public_items_response.json()[0]["label"] == "测试项"
    finally:
        if type_id:
            _delete_dictionary_type(
                client,
                superuser_token_headers,
                type_id,
                item_id,
            )


def test_dictionary_item_value_must_be_unique_in_type(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    dictionary_code = f"dict_{random_lower_string()}"
    type_id: str | None = None
    item_id: str | None = None
    try:
        create_type_response = client.post(
            f"{settings.API_V1_STR}/dictionary-types",
            headers=superuser_token_headers,
            json={
                "code": dictionary_code,
                "name": "测试字典",
                "is_active": True,
            },
        )
        assert create_type_response.status_code == 200
        type_id = create_type_response.json()["id"]

        payload = {
            "type_id": type_id,
            "label": "测试项",
            "value": "same",
            "sort": 0,
            "is_active": True,
        }
        create_item_response = client.post(
            f"{settings.API_V1_STR}/dictionary-items",
            headers=superuser_token_headers,
            json=payload,
        )
        assert create_item_response.status_code == 200
        item_id = create_item_response.json()["id"]

        duplicate_response = client.post(
            f"{settings.API_V1_STR}/dictionary-items",
            headers=superuser_token_headers,
            json={**payload, "label": "重复项"},
        )
        assert duplicate_response.status_code == 409
    finally:
        if type_id:
            _delete_dictionary_type(
                client,
                superuser_token_headers,
                type_id,
                item_id,
            )


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


def test_public_settings_use_cached_payload(client: TestClient, monkeypatch) -> None:
    cache_store: dict[str, list[dict[str, object]]] = {}

    def fake_get_json(key: str) -> list[dict[str, object]] | None:
        return cache_store.get(key)

    def fake_set_json(
        key: str,
        value: list[dict[str, object]],
        *,
        _ttl_seconds: int | None = None,
    ) -> None:
        cache_store[key] = value

    monkeypatch.setattr(redis_cache, "get_json", fake_get_json)
    monkeypatch.setattr(redis_cache, "set_json", fake_set_json)

    first_response = client.get(f"{settings.API_V1_STR}/settings/public")
    assert first_response.status_code == 200
    assert cache_store

    cache_key = next(iter(cache_store))
    cache_store[cache_key][0]["value"] = "Cached Settings Value"

    second_response = client.get(f"{settings.API_V1_STR}/settings/public")
    assert second_response.status_code == 200
    assert any(
        setting["value"] == "Cached Settings Value"
        for setting in second_response.json()
    )


def test_updating_setting_bumps_public_settings_cache_namespace(
    client: TestClient, superuser_token_headers: dict[str, str], monkeypatch
) -> None:
    bumped_namespaces: list[str] = []
    monkeypatch.setattr(
        redis_cache,
        "bump_namespace",
        lambda namespace: bumped_namespaces.append(namespace),
    )

    response = client.patch(
        f"{settings.API_V1_STR}/settings/system.name",
        headers=superuser_token_headers,
        json={"value": "Fast Vben Admin Cache Test"},
    )

    assert response.status_code == 200
    assert CacheNamespace.PUBLIC_SETTINGS in bumped_namespaces


def test_json_setting_value_must_be_valid_json(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.patch(
        f"{settings.API_V1_STR}/settings/system.name",
        headers=superuser_token_headers,
        json={"value_type": "json", "value": "{not-json"},
    )

    assert response.status_code == 400
    assert response.json()["message"] == "Setting value must be JSON"


def test_updating_dictionary_item_bumps_dictionary_cache_namespace(
    client: TestClient, superuser_token_headers: dict[str, str], monkeypatch
) -> None:
    bumped_namespaces: list[str] = []
    monkeypatch.setattr(
        redis_cache,
        "bump_namespace",
        lambda namespace: bumped_namespaces.append(namespace),
    )
    dictionary_code = f"dict_{random_lower_string()}"
    type_id: str | None = None
    item_id: str | None = None
    try:
        create_type_response = client.post(
            f"{settings.API_V1_STR}/dictionary-types",
            headers=superuser_token_headers,
            json={
                "code": dictionary_code,
                "name": "测试字典",
                "is_active": True,
            },
        )
        assert create_type_response.status_code == 200
        type_id = create_type_response.json()["id"]

        create_item_response = client.post(
            f"{settings.API_V1_STR}/dictionary-items",
            headers=superuser_token_headers,
            json={
                "type_id": type_id,
                "label": "测试项",
                "value": "cache-test",
                "sort": 0,
                "is_active": True,
            },
        )
        assert create_item_response.status_code == 200
        item_id = create_item_response.json()["id"]

        update_response = client.patch(
            f"{settings.API_V1_STR}/dictionary-items/{item_id}",
            headers=superuser_token_headers,
            json={"label": "更新后的测试项"},
        )
        assert update_response.status_code == 200
        assert CacheNamespace.DICTIONARY_ITEMS in bumped_namespaces
    finally:
        if type_id:
            _delete_dictionary_type(
                client,
                superuser_token_headers,
                type_id,
                item_id,
            )


def test_dictionaries_and_settings_are_isolated_between_tenants(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    monkeypatch,
) -> None:
    dictionary_code = f"tenant_dict_{random_lower_string()}"
    tenant_id: str | None = None
    default_type_id: str | None = None
    default_item_id: str | None = None
    tenant_type_id: str | None = None
    cache_store: dict[str, list[dict[str, object]]] = {}

    monkeypatch.setattr(redis_cache, "get_json", lambda key: cache_store.get(key))
    monkeypatch.setattr(
        redis_cache,
        "set_json",
        lambda key, value, **_kwargs: cache_store.__setitem__(key, value),
    )

    try:
        default_type_response = client.post(
            f"{settings.API_V1_STR}/dictionary-types",
            headers=superuser_token_headers,
            json={
                "code": dictionary_code,
                "name": "测试字典",
                "is_active": True,
            },
        )
        assert default_type_response.status_code == 200
        default_type = default_type_response.json()
        default_type_id = default_type["id"]
        assert default_type["tenant_id"] == str(DEFAULT_TENANT_ID)

        default_item_response = client.post(
            f"{settings.API_V1_STR}/dictionary-items",
            headers=superuser_token_headers,
            json={
                "type_id": default_type_id,
                "label": "Default item",
                "value": "shared",
            },
        )
        assert default_item_response.status_code == 200
        default_item_id = default_item_response.json()["id"]

        tenant_response = client.post(
            f"{settings.API_V1_STR}/tenants",
            headers=superuser_token_headers,
            json={
                "code": f"config-{random_lower_string()}",
                "name": "Configuration isolation tenant",
            },
        )
        assert tenant_response.status_code == 200
        tenant_id = tenant_response.json()["id"]

        switch_response = client.post(
            f"{settings.API_V1_STR}/tenants/switch",
            headers=superuser_token_headers,
            json={"tenant_id": tenant_id},
        )
        assert switch_response.status_code == 200
        tenant_headers = {
            "Authorization": f"Bearer {switch_response.json()['access_token']}"
        }

        tenant_type_response = client.post(
            f"{settings.API_V1_STR}/dictionary-types",
            headers=tenant_headers,
            json={
                "code": dictionary_code,
                "name": "测试字典",
                "is_active": True,
            },
        )
        assert tenant_type_response.status_code == 200
        tenant_type = tenant_type_response.json()
        tenant_type_id = tenant_type["id"]
        assert tenant_type["tenant_id"] == tenant_id
        assert tenant_type_id != default_type_id

        tenant_item_response = client.post(
            f"{settings.API_V1_STR}/dictionary-items",
            headers=tenant_headers,
            json={
                "type_id": tenant_type_id,
                "label": "Tenant item",
                "value": "shared",
            },
        )
        assert tenant_item_response.status_code == 200
        assert tenant_item_response.json()["tenant_id"] == tenant_id

        tenant_items_response = client.get(
            f"{settings.API_V1_STR}/dictionary-items",
            headers=tenant_headers,
            params={"type_id": default_type_id},
        )
        assert tenant_items_response.status_code == 200
        assert tenant_items_response.json()["items"] == []
        assert (
            client.patch(
                f"{settings.API_V1_STR}/dictionary-items/{default_item_id}",
                headers=tenant_headers,
                json={"label": "Cross-tenant update"},
            ).status_code
            == 404
        )
        assert (
            client.delete(
                f"{settings.API_V1_STR}/dictionary-items/{default_item_id}",
                headers=tenant_headers,
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"{settings.API_V1_STR}/dictionary-items",
                headers=tenant_headers,
                json={
                    "type_id": default_type_id,
                    "label": "Cross-tenant item",
                    "value": "blocked",
                },
            ).status_code
            == 400
        )

        db.add(
            DictionaryItem(
                tenant_id=tenant_id,
                type_id=default_type_id,
                label="Invalid tenant binding",
                value="invalid",
            )
        )
        try:
            db.commit()
            raise AssertionError("Cross-tenant dictionary item unexpectedly succeeded")
        except IntegrityError:
            db.rollback()

        tenant_name = f"Tenant Name {random_lower_string()}"
        update_setting_response = client.patch(
            f"{settings.API_V1_STR}/settings/system.name",
            headers=tenant_headers,
            json={"value": tenant_name},
        )
        assert update_setting_response.status_code == 200
        assert update_setting_response.json()["tenant_id"] == tenant_id

        default_headers = get_superuser_token_headers(client)
        default_dictionary_response = client.get(
            f"{settings.API_V1_STR}/dictionaries/{dictionary_code}/items",
            headers=default_headers,
        )
        tenant_dictionary_response = client.get(
            f"{settings.API_V1_STR}/dictionaries/{dictionary_code}/items",
            headers=tenant_headers,
        )
        assert default_dictionary_response.status_code == 200
        assert tenant_dictionary_response.status_code == 200
        assert default_dictionary_response.json()[0]["label"] == "Default item"
        assert tenant_dictionary_response.json()[0]["label"] == "Tenant item"

        tenant_public_response = client.get(
            f"{settings.API_V1_STR}/settings/public",
            headers=tenant_headers,
        )
        default_public_response = client.get(f"{settings.API_V1_STR}/settings/public")
        assert tenant_public_response.status_code == 200
        assert default_public_response.status_code == 200
        tenant_public = {
            setting["key"]: setting for setting in tenant_public_response.json()
        }
        default_public = {
            setting["key"]: setting for setting in default_public_response.json()
        }
        assert tenant_public["system.name"]["value"] == tenant_name
        assert tenant_public["system.name"]["tenant_id"] == tenant_id
        assert default_public["system.name"]["value"] != tenant_name
        assert default_public["system.name"]["tenant_id"] == str(DEFAULT_TENANT_ID)
        assert len(cache_store) == 4

        seeded_dictionary_response = client.get(
            f"{settings.API_V1_STR}/dictionaries/user_status/items",
            headers=tenant_headers,
        )
        assert seeded_dictionary_response.status_code == 200
        assert {item["value"] for item in seeded_dictionary_response.json()} >= {
            "active",
            "inactive",
        }
        assert (
            len(
                db.exec(
                    select(DictionaryType).where(DictionaryType.code == dictionary_code)
                ).all()
            )
            == 2
        )
        assert (
            len(
                db.exec(
                    select(SystemSetting).where(
                        SystemSetting.key == "system.name",
                        SystemSetting.tenant_id.in_([DEFAULT_TENANT_ID, tenant_id]),
                    )
                ).all()
            )
            == 2
        )
    finally:
        db.rollback()
        if default_item_id is not None:
            db.exec(delete(DictionaryItem).where(DictionaryItem.id == default_item_id))
        if default_type_id is not None:
            db.exec(delete(DictionaryType).where(DictionaryType.id == default_type_id))
        if tenant_id is not None:
            db.exec(delete(UserSession).where(UserSession.tenant_id == tenant_id))
            db.exec(delete(UserPost).where(UserPost.tenant_id == tenant_id))
            db.exec(delete(UserRole).where(UserRole.tenant_id == tenant_id))
            db.exec(
                delete(TenantMembership).where(TenantMembership.tenant_id == tenant_id)
            )
            for role in db.exec(select(Role).where(Role.tenant_id == tenant_id)).all():
                db.delete(role)
            db.commit()
            tenant = db.get(Tenant, tenant_id)
            if tenant is not None:
                db.delete(tenant)
        db.commit()
