import re
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import crud
from app.core.cache import CacheNamespace, redis_cache
from app.core.config import settings
from app.models import (
    DataScope,
    Department,
    Menu,
    Role,
    RoleMenu,
    Tenant,
    UserCreate,
    UserRole,
)
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_lower_string


def test_required_permissions_are_seeded(db: Session) -> None:
    backend_root = Path(__file__).resolve().parents[3]
    permission_pattern = re.compile(r'require_permission\("([^"]+)"\)')
    required_permissions: set[str] = set()

    for route_file in (backend_root / "app" / "api" / "routes").glob("*.py"):
        required_permissions.update(
            permission_pattern.findall(route_file.read_text(encoding="utf-8"))
        )

    seeded_permissions = {
        permission
        for permission in db.exec(select(Menu.permission_code)).all()
        if permission
    }

    assert required_permissions <= seeded_permissions


def test_seeded_menu_components_exist(db: Session) -> None:
    project_root = Path(__file__).resolve().parents[4]
    frontend_src = project_root / "frontend" / "apps" / "web-antd" / "src"
    menus = db.exec(select(Menu).where(Menu.component != None)).all()  # noqa: E711

    missing_components = []
    for menu in menus:
        assert menu.component
        if not menu.component.startswith("#/"):
            continue
        component_path = frontend_src / menu.component.removeprefix("#/")
        if not component_path.exists():
            missing_components.append(menu.component)

    assert missing_components == []


def test_basic_settings_menu_hierarchy(db: Session) -> None:
    basic_settings = db.exec(
        select(Menu).where(Menu.route_path == "/basic-settings")
    ).one()
    system_settings = db.exec(
        select(Menu).where(Menu.permission_code == "system:setting:list")
    ).one()
    files = db.exec(
        select(Menu).where(Menu.route_path == "/basic-settings/files")
    ).one()
    message_center = db.exec(
        select(Menu).where(Menu.route_name == "MessageCenter")
    ).one()
    notices = db.exec(
        select(Menu).where(Menu.route_path == "/system/message-center/notices")
    ).one()
    messages = db.exec(
        select(Menu).where(Menu.route_path == "/system/message-center/messages")
    ).one()
    file_children = db.exec(select(Menu).where(Menu.parent_id == files.id)).all()

    assert basic_settings.parent_id is None
    assert basic_settings.title == "menu.infrastructure"
    assert basic_settings.sort == 15
    assert system_settings.parent_id == basic_settings.id
    assert system_settings.route_path == "/basic-settings/settings"
    assert files.parent_id == basic_settings.id
    assert {menu.route_path for menu in file_children} == {
        "/basic-settings/files/channels",
        "/basic-settings/files/config",
        "/basic-settings/files/list",
    }
    assert message_center.route_path == "/system/message-center"
    assert notices.parent_id == message_center.id
    assert messages.parent_id == message_center.id


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


def test_list_pagination_is_normalized(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    invalid_response = client.get(
        f"{settings.API_V1_STR}/roles",
        headers=superuser_token_headers,
        params={"page": 0},
    )
    assert invalid_response.status_code == 422

    capped_response = client.get(
        f"{settings.API_V1_STR}/roles",
        headers=superuser_token_headers,
        params={"page_size": 1000},
    )
    assert capped_response.status_code == 200
    assert capped_response.json()["page_size"] == 100


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


def test_superuser_permissions_use_cached_payload(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    monkeypatch,
) -> None:
    cache_store: dict[str, list[str]] = {}

    def fake_get_json(key: str) -> list[str] | None:
        return cache_store.get(key)

    def fake_set_json(
        key: str, value: list[str], *, _ttl_seconds: int | None = None
    ) -> None:
        cache_store[key] = value

    monkeypatch.setattr(redis_cache, "get_json", fake_get_json)
    monkeypatch.setattr(redis_cache, "set_json", fake_set_json)

    first_response = client.get(
        f"{settings.API_V1_STR}/permissions/me",
        headers=superuser_token_headers,
    )
    assert first_response.status_code == 200
    assert cache_store

    cache_key = next(iter(cache_store))
    cache_store[cache_key] = [*cache_store[cache_key], "cached:permission"]

    second_response = client.get(
        f"{settings.API_V1_STR}/permissions/me",
        headers=superuser_token_headers,
    )
    assert second_response.status_code == 200
    assert "cached:permission" in second_response.json()


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
            "name": f"测试角色_{role_code}",
            "description": "RBAC test role",
            "sort": 90,
            "is_active": True,
            "is_system": False,
        },
    )

    assert create_role_response.status_code == 200
    role = create_role_response.json()
    assert role["code"] == role_code

    try:
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
    finally:
        delete_response = client.delete(
            f"{settings.API_V1_STR}/roles/{role['id']}",
            headers=superuser_token_headers,
        )
        assert delete_response.status_code == 204


def test_role_custom_departments_reject_cross_tenant_bindings(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    default_tenant = db.exec(select(Tenant).where(Tenant.code == "default")).one()
    suffix = random_lower_string()
    local_department = Department(
        tenant_id=default_tenant.id,
        code=f"role-scope-local-{suffix}",
        name="Local scope department",
    )
    other_tenant = Tenant(
        code=f"role-scope-tenant-{suffix}",
        name="Role scope tenant",
    )
    db.add_all([local_department, other_tenant])
    db.flush()
    other_department = Department(
        tenant_id=other_tenant.id,
        code=f"role-scope-other-{suffix}",
        name="Other scope department",
    )
    db.add(other_department)
    db.commit()

    role_id: str | None = None
    try:
        create_response = client.post(
            f"{settings.API_V1_STR}/roles",
            headers=superuser_token_headers,
            json={
                "code": f"custom_scope_{suffix}",
                "name": "Custom scope role",
                "data_scope": "custom",
                "custom_department_ids": [str(local_department.id)],
            },
        )
        assert create_response.status_code == 200
        role = create_response.json()
        role_id = role["id"]
        assert role["data_scope"] == "custom"
        assert role["custom_department_ids"] == [str(local_department.id)]

        invalid_response = client.patch(
            f"{settings.API_V1_STR}/roles/{role_id}",
            headers=superuser_token_headers,
            json={"custom_department_ids": [str(other_department.id)]},
        )
        assert invalid_response.status_code == 400

        read_response = client.get(
            f"{settings.API_V1_STR}/roles/{role_id}",
            headers=superuser_token_headers,
        )
        assert read_response.status_code == 200
        assert read_response.json()["custom_department_ids"] == [
            str(local_department.id)
        ]
    finally:
        if role_id is not None:
            assert (
                client.delete(
                    f"{settings.API_V1_STR}/roles/{role_id}",
                    headers=superuser_token_headers,
                ).status_code
                == 204
            )
        db.delete(local_department)
        db.delete(other_department)
        db.commit()
        db.delete(other_tenant)
        db.commit()


def test_updating_role_menus_bumps_rbac_cache_namespace(
    client: TestClient, superuser_token_headers: dict[str, str], monkeypatch
) -> None:
    bumped_namespaces: list[str] = []
    monkeypatch.setattr(
        redis_cache,
        "bump_namespace",
        lambda namespace: bumped_namespaces.append(namespace),
    )
    role_code = f"role_{random_lower_string()}"
    create_role_response = client.post(
        f"{settings.API_V1_STR}/roles",
        headers=superuser_token_headers,
        json={
            "code": role_code,
            "name": f"测试角色_{role_code}",
            "description": "RBAC cache invalidation test",
            "sort": 95,
            "is_active": True,
            "is_system": False,
        },
    )
    assert create_role_response.status_code == 200
    role = create_role_response.json()

    try:
        menus_response = client.get(
            f"{settings.API_V1_STR}/menus",
            headers=superuser_token_headers,
        )
        assert menus_response.status_code == 200
        menu_ids = [
            menu["id"]
            for menu in menus_response.json()["items"]
            if menu["permission_code"] == "system:user:list"
        ]
        assert len(menu_ids) == 1

        assign_response = client.put(
            f"{settings.API_V1_STR}/roles/{role['id']}/menus",
            headers=superuser_token_headers,
            json={"menu_ids": menu_ids},
        )
        assert assign_response.status_code == 200
        assert CacheNamespace.RBAC in bumped_namespaces
    finally:
        delete_response = client.delete(
            f"{settings.API_V1_STR}/roles/{role['id']}",
            headers=superuser_token_headers,
        )
        assert delete_response.status_code == 204


def test_superuser_can_create_department(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    department_code = f"dept_{random_lower_string()}"
    response = client.post(
        f"{settings.API_V1_STR}/departments",
        headers=superuser_token_headers,
        json={
            "code": department_code,
            "name": f"测试部门_{department_code}",
            "sort": 10,
            "is_active": True,
        },
    )

    assert response.status_code == 200
    department = response.json()
    assert department["code"] == department_code
    assert department["name"] == f"测试部门_{department_code}"

    delete_response = client.delete(
        f"{settings.API_V1_STR}/departments/{department['id']}",
        headers=superuser_token_headers,
    )
    assert delete_response.status_code == 204


def test_disabled_role_does_not_grant_permissions(
    client: TestClient, db: Session
) -> None:
    password = random_lower_string()
    user = crud.create_user(
        session=db,
        user_create=UserCreate(
            email=f"{random_lower_string()}@example.com",
            password=password,
        ),
    )
    role = Role(
        code=f"disabled_{random_lower_string()}",
        name="Disabled role",
        is_active=False,
    )
    db.add(role)
    db.flush()
    menu = db.exec(
        select(Menu).where(Menu.permission_code == "system:role:list")
    ).first()
    assert menu
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.add(RoleMenu(role_id=role.id, menu_id=menu.id))
    db.commit()

    headers = user_authentication_headers(
        client=client,
        email=user.email,
        password=password,
    )
    try:
        response = client.get(f"{settings.API_V1_STR}/roles", headers=headers)
        assert response.status_code == 403

        permissions_response = client.get(
            f"{settings.API_V1_STR}/permissions/me",
            headers=headers,
        )
        assert permissions_response.status_code == 200
        assert "system:role:list" not in permissions_response.json()
    finally:
        db.delete(user)
        db.delete(role)
        db.commit()


def test_non_superuser_with_user_permission_can_read_users(
    client: TestClient, db: Session
) -> None:
    password = random_lower_string()
    user = crud.create_user(
        session=db,
        user_create=UserCreate(
            email=f"{random_lower_string()}@example.com",
            password=password,
        ),
    )
    role = Role(
        code=f"user_manager_{random_lower_string()}",
        name="User manager",
        is_active=True,
    )
    db.add(role)
    db.flush()
    menu = db.exec(
        select(Menu).where(Menu.permission_code == "system:user:list")
    ).first()
    assert menu
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.add(RoleMenu(role_id=role.id, menu_id=menu.id))
    db.commit()

    headers = user_authentication_headers(
        client=client,
        email=user.email,
        password=password,
    )
    try:
        response = client.get(f"{settings.API_V1_STR}/users", headers=headers)
        assert response.status_code == 200
        assert "items" in response.json()
    finally:
        db.delete(user)
        db.delete(role)
        db.commit()


def test_user_management_honors_department_data_scope(
    client: TestClient, db: Session
) -> None:
    tenant = db.exec(select(Tenant).where(Tenant.code == "default")).one()
    suffix = random_lower_string()
    department = Department(
        tenant_id=tenant.id,
        code=f"user-scope-local-{suffix}",
        name="User scope local",
    )
    other_department = Department(
        tenant_id=tenant.id,
        code=f"user-scope-other-{suffix}",
        name="User scope other",
    )
    db.add_all([department, other_department])
    db.commit()
    password = random_lower_string()

    def create_user_in(department_id):
        return crud.create_user(
            session=db,
            user_create=UserCreate(
                email=f"{random_lower_string()}@example.com",
                password=password,
                department_id=department_id,
            ),
            tenant_id=tenant.id,
        )

    manager = create_user_in(department.id)
    peer = create_user_in(department.id)
    outsider = create_user_in(other_department.id)
    role = Role(
        tenant_id=tenant.id,
        code=f"user_scope_{suffix}",
        name="User scope manager",
        data_scope=DataScope.DEPARTMENT,
    )
    db.add(role)
    db.flush()
    permission_menus = db.exec(
        select(Menu).where(
            Menu.permission_code.in_(
                {"system:user:list", "system:user:update", "system:user:delete"}
            )
        )
    ).all()
    db.add(UserRole(user_id=manager.id, role_id=role.id, tenant_id=tenant.id))
    for menu in permission_menus:
        db.add(RoleMenu(role_id=role.id, menu_id=menu.id))
    db.commit()
    headers = user_authentication_headers(
        client=client,
        email=manager.email,
        password=password,
    )

    try:
        list_response = client.get(
            f"{settings.API_V1_STR}/users",
            headers=headers,
            params={"page_size": 100},
        )
        assert list_response.status_code == 200
        visible_ids = {user["id"] for user in list_response.json()["items"]}
        assert str(manager.id) in visible_ids
        assert str(peer.id) in visible_ids
        assert str(outsider.id) not in visible_ids

        export_response = client.get(
            f"{settings.API_V1_STR}/users/export", headers=headers
        )
        assert export_response.status_code == 200
        assert peer.email in export_response.text
        assert outsider.email not in export_response.text

        assert (
            client.get(
                f"{settings.API_V1_STR}/users/{peer.id}", headers=headers
            ).status_code
            == 200
        )
        assert (
            client.get(
                f"{settings.API_V1_STR}/users/{outsider.id}", headers=headers
            ).status_code
            == 403
        )
        assert (
            client.patch(
                f"{settings.API_V1_STR}/users/{outsider.id}",
                headers=headers,
                json={"full_name": "must-not-update"},
            ).status_code
            == 403
        )
        assert (
            client.delete(
                f"{settings.API_V1_STR}/users/{outsider.id}", headers=headers
            ).status_code
            == 403
        )
    finally:
        for user in [manager, peer, outsider]:
            db.delete(user)
        db.commit()
        db.delete(role)
        db.commit()
        db.delete(department)
        db.delete(other_department)
        db.commit()


def test_menu_parent_cannot_be_descendant(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    root_response = client.post(
        f"{settings.API_V1_STR}/menus",
        headers=superuser_token_headers,
        json={
            "title": f"root_{random_lower_string()}",
            "type": "directory",
            "route_path": f"/root-{random_lower_string()}",
            "route_name": f"Root{random_lower_string()}",
            "sort": 900,
        },
    )
    assert root_response.status_code == 200
    root = root_response.json()
    child_response = client.post(
        f"{settings.API_V1_STR}/menus",
        headers=superuser_token_headers,
        json={
            "title": f"child_{random_lower_string()}",
            "type": "menu",
            "parent_id": root["id"],
            "route_path": f"/child-{random_lower_string()}",
            "route_name": f"Child{random_lower_string()}",
            "component": "#/views/items/index.vue",
            "sort": 901,
        },
    )
    assert child_response.status_code == 200
    child = child_response.json()
    try:
        response = client.patch(
            f"{settings.API_V1_STR}/menus/{root['id']}",
            headers=superuser_token_headers,
            json={"parent_id": child["id"]},
        )
        assert response.status_code == 400
    finally:
        client.delete(
            f"{settings.API_V1_STR}/menus/{child['id']}",
            headers=superuser_token_headers,
        )
        client.delete(
            f"{settings.API_V1_STR}/menus/{root['id']}",
            headers=superuser_token_headers,
        )


def test_department_parent_cannot_be_descendant(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    root_code = f"dept_{random_lower_string()}"
    child_code = f"dept_{random_lower_string()}"
    root_response = client.post(
        f"{settings.API_V1_STR}/departments",
        headers=superuser_token_headers,
        json={"code": root_code, "name": root_code, "sort": 900},
    )
    assert root_response.status_code == 200
    root = root_response.json()
    child_response = client.post(
        f"{settings.API_V1_STR}/departments",
        headers=superuser_token_headers,
        json={
            "code": child_code,
            "name": child_code,
            "parent_id": root["id"],
            "sort": 901,
        },
    )
    assert child_response.status_code == 200
    child = child_response.json()
    try:
        response = client.patch(
            f"{settings.API_V1_STR}/departments/{root['id']}",
            headers=superuser_token_headers,
            json={"parent_id": child["id"]},
        )
        assert response.status_code == 400
    finally:
        client.delete(
            f"{settings.API_V1_STR}/departments/{child['id']}",
            headers=superuser_token_headers,
        )
        client.delete(
            f"{settings.API_V1_STR}/departments/{root['id']}",
            headers=superuser_token_headers,
        )
