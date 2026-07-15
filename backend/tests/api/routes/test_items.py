import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, col, delete, select

from app import crud
from app.core.config import settings
from app.models import (
    DataScope,
    Department,
    Item,
    Menu,
    Role,
    RoleDataScopeDepartment,
    RoleMenu,
    Tenant,
    TenantMembership,
    UserCreate,
    UserRole,
)
from tests.utils.item import create_random_item
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string


def test_create_item(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {"title": "Foo", "description": "Fighters"}
    response = client.post(
        f"{settings.API_V1_STR}/items",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["title"] == data["title"]
    assert content["description"] == data["description"]
    assert "id" in content
    assert "owner_id" in content
    assert "created_at" in content
    assert "updated_at" in content


def test_read_item(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    item = create_random_item(db)
    response = client.get(
        f"{settings.API_V1_STR}/items/{item.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["title"] == item.title
    assert content["description"] == item.description
    assert content["id"] == str(item.id)
    assert content["owner_id"] == str(item.owner_id)


def test_read_item_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/items/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["code"] == "NOT_FOUND"
    assert content["message"] == "Item not found"


def test_read_item_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    item = create_random_item(db)
    response = client.get(
        f"{settings.API_V1_STR}/items/{item.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
    content = response.json()
    assert content["code"] == "ITEM_FORBIDDEN"
    assert content["message"] == "Not enough permissions"


def test_read_items(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    create_random_item(db)
    create_random_item(db)
    response = client.get(
        f"{settings.API_V1_STR}/items",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert len(content["items"]) >= 2
    assert "total" in content
    assert content["page"] == 1
    assert content["page_size"] == 20


def test_export_items(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/items/export",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "title" in response.text


def test_import_items(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/items/import",
        headers=superuser_token_headers,
        files={"file": ("items.csv", "title,description\n导入资源,描述\n,缺少标题\n")},
    )
    assert response.status_code == 200
    content = response.json()
    assert content["success"] == 1
    assert content["failed"] == 1
    assert content["errors"][0]["row"] == 3


def test_update_item(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    item = create_random_item(db)
    data = {"title": "Updated title", "description": "Updated description"}
    response = client.patch(
        f"{settings.API_V1_STR}/items/{item.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["title"] == data["title"]
    assert content["description"] == data["description"]
    assert content["id"] == str(item.id)
    assert content["owner_id"] == str(item.owner_id)


def test_update_item_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {"title": "Updated title", "description": "Updated description"}
    response = client.patch(
        f"{settings.API_V1_STR}/items/{uuid.uuid4()}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["code"] == "NOT_FOUND"
    assert content["message"] == "Item not found"


def test_update_item_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    item = create_random_item(db)
    data = {"title": "Updated title", "description": "Updated description"}
    response = client.patch(
        f"{settings.API_V1_STR}/items/{item.id}",
        headers=normal_user_token_headers,
        json=data,
    )
    assert response.status_code == 403
    content = response.json()
    assert content["code"] == "ITEM_FORBIDDEN"
    assert content["message"] == "Not enough permissions"


def test_delete_item(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    item = create_random_item(db)
    response = client.delete(
        f"{settings.API_V1_STR}/items/{item.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 204
    assert not response.content


def test_delete_item_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/items/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["code"] == "NOT_FOUND"
    assert content["message"] == "Item not found"


def test_delete_item_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    item = create_random_item(db)
    response = client.delete(
        f"{settings.API_V1_STR}/items/{item.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
    content = response.json()
    assert content["code"] == "ITEM_FORBIDDEN"
    assert content["message"] == "Not enough permissions"


def test_items_are_isolated_between_tenants(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    tenant = Tenant(
        code=f"tenant-{random_lower_string()}",
        name="Isolation test tenant",
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    password = random_lower_string()
    user = crud.create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password=password),
    )
    memberships = db.exec(
        select(TenantMembership).where(TenantMembership.user_id == user.id)
    ).all()
    for membership in memberships:
        membership.is_default = False
        db.add(membership)
    db.add(
        TenantMembership(
            user_id=user.id,
            tenant_id=tenant.id,
            is_default=True,
        )
    )
    tenant_role = Role(
        tenant_id=tenant.id,
        code=f"item-user-{random_lower_string()}",
        name="Tenant item user",
    )
    db.add(tenant_role)
    db.flush()
    item_menus = db.exec(
        select(Menu).where(
            Menu.permission_code.in_(
                {
                    "business:item:create",
                    "business:item:delete",
                    "business:item:list",
                    "business:item:update",
                }
            )
        )
    ).all()
    db.add(
        UserRole(
            user_id=user.id,
            role_id=tenant_role.id,
            tenant_id=tenant.id,
        )
    )
    for menu in item_menus:
        db.add(RoleMenu(role_id=tenant_role.id, menu_id=menu.id))
    db.commit()

    tenant_headers = user_authentication_headers(
        client=client,
        email=user.email,
        password=password,
    )
    title = f"isolated-{random_lower_string()}"
    create_response = client.post(
        f"{settings.API_V1_STR}/items",
        headers=tenant_headers,
        json={"title": title, "description": "tenant boundary"},
    )
    assert create_response.status_code == 200
    item_id = create_response.json()["id"]
    assert create_response.json()["tenant_id"] == str(tenant.id)

    try:
        read_response = client.get(
            f"{settings.API_V1_STR}/items/{item_id}",
            headers=superuser_token_headers,
        )
        assert read_response.status_code == 404

        list_response = client.get(
            f"{settings.API_V1_STR}/items",
            headers=superuser_token_headers,
        )
        assert list_response.status_code == 200
        assert item_id not in {item["id"] for item in list_response.json()["items"]}

        export_response = client.get(
            f"{settings.API_V1_STR}/items/export",
            headers=superuser_token_headers,
        )
        assert export_response.status_code == 200
        assert title not in export_response.text

        update_response = client.patch(
            f"{settings.API_V1_STR}/items/{item_id}",
            headers=superuser_token_headers,
            json={"title": "cross-tenant update"},
        )
        assert update_response.status_code == 404

        delete_response = client.delete(
            f"{settings.API_V1_STR}/items/{item_id}",
            headers=superuser_token_headers,
        )
        assert delete_response.status_code == 404
    finally:
        item = db.get(Item, uuid.UUID(item_id))
        if item is not None:
            db.delete(item)
            db.commit()
        db.delete(user)
        db.commit()
        db.delete(tenant_role)
        db.commit()
        db.delete(tenant)
        db.commit()


def test_item_data_scopes_and_role_unions(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    tenant = db.exec(select(Tenant).where(Tenant.code == "default")).one()
    suffix = random_lower_string()
    root = Department(
        tenant_id=tenant.id,
        code=f"scope-root-{suffix}",
        name="Scope root",
    )
    child = Department(
        tenant_id=tenant.id,
        code=f"scope-child-{suffix}",
        name="Scope child",
    )
    custom = Department(
        tenant_id=tenant.id,
        code=f"scope-custom-{suffix}",
        name="Scope custom",
    )
    other = Department(
        tenant_id=tenant.id,
        code=f"scope-other-{suffix}",
        name="Scope other",
    )
    db.add_all([root, custom, other])
    db.flush()
    child.parent_id = root.id
    db.add(child)
    db.commit()

    password = random_lower_string()

    def create_scoped_user(label: str, department: Department):
        return crud.create_user(
            session=db,
            user_create=UserCreate(
                email=random_email(),
                password=password,
                full_name=label,
                department_id=department.id,
            ),
            tenant_id=tenant.id,
        )

    manager = create_scoped_user("scope-manager", root)
    same_department_user = create_scoped_user("scope-same", root)
    child_user = create_scoped_user("scope-child", child)
    custom_user = create_scoped_user("scope-custom", custom)
    other_user = create_scoped_user("scope-other", other)
    role = Role(
        tenant_id=tenant.id,
        code=f"scope-role-{suffix}",
        name="Scope test role",
        data_scope=DataScope.SELF,
    )
    db.add(role)
    db.flush()
    item_menus = db.exec(
        select(Menu).where(
            Menu.permission_code.in_(
                {
                    "business:item:create",
                    "business:item:delete",
                    "business:item:list",
                    "business:item:update",
                }
            )
        )
    ).all()
    db.add(UserRole(user_id=manager.id, role_id=role.id, tenant_id=tenant.id))
    for menu in item_menus:
        db.add(RoleMenu(role_id=role.id, menu_id=menu.id))

    owners = {
        "self": manager,
        "same": same_department_user,
        "child": child_user,
        "custom": custom_user,
        "other": other_user,
    }
    items = {
        label: Item(
            title=f"scope-{label}-{suffix}",
            owner_id=owner.id,
            tenant_id=tenant.id,
        )
        for label, owner in owners.items()
    }
    db.add_all(items.values())
    db.commit()

    headers = user_authentication_headers(
        client=client,
        email=manager.email,
        password=password,
    )
    expected_by_scope = {
        DataScope.SELF: {"self"},
        DataScope.DEPARTMENT: {"self", "same"},
        DataScope.DEPARTMENT_AND_CHILDREN: {"self", "same", "child"},
        DataScope.CUSTOM: {"self", "custom"},
        DataScope.ALL: set(items),
    }

    try:
        for data_scope, expected_labels in expected_by_scope.items():
            role.data_scope = data_scope
            db.add(role)
            db.exec(
                delete(RoleDataScopeDepartment).where(
                    RoleDataScopeDepartment.role_id == role.id
                )
            )
            if data_scope == DataScope.CUSTOM:
                db.add(
                    RoleDataScopeDepartment(
                        role_id=role.id,
                        department_id=custom.id,
                        tenant_id=tenant.id,
                    )
                )
            db.commit()

            response = client.get(
                f"{settings.API_V1_STR}/items",
                headers=headers,
                params={"page_size": 100},
            )
            assert response.status_code == 200
            visible_ids = {item["id"] for item in response.json()["items"]}
            assert {
                label for label, item in items.items() if str(item.id) in visible_ids
            } == expected_labels

            export_response = client.get(
                f"{settings.API_V1_STR}/items/export", headers=headers
            )
            assert export_response.status_code == 200
            assert {
                label
                for label, item in items.items()
                if item.title in export_response.text
            } == expected_labels

        role.data_scope = DataScope.DEPARTMENT_AND_CHILDREN
        db.add(role)
        db.commit()
        assert (
            client.get(
                f"{settings.API_V1_STR}/items/{items['child'].id}", headers=headers
            ).status_code
            == 200
        )
        assert (
            client.patch(
                f"{settings.API_V1_STR}/items/{items['other'].id}",
                headers=headers,
                json={"title": "must-not-update"},
            ).status_code
            == 403
        )
        assert (
            client.delete(
                f"{settings.API_V1_STR}/items/{items['other'].id}", headers=headers
            ).status_code
            == 403
        )

        union_role = Role(
            tenant_id=tenant.id,
            code=f"scope-union-{suffix}",
            name="Scope union role",
            data_scope=DataScope.CUSTOM,
        )
        db.add(union_role)
        db.flush()
        db.add(
            UserRole(
                user_id=manager.id,
                role_id=union_role.id,
                tenant_id=tenant.id,
            )
        )
        db.add(
            RoleDataScopeDepartment(
                role_id=union_role.id,
                department_id=custom.id,
                tenant_id=tenant.id,
            )
        )
        db.commit()
        union_response = client.get(
            f"{settings.API_V1_STR}/items",
            headers=headers,
            params={"page_size": 100},
        )
        union_ids = {item["id"] for item in union_response.json()["items"]}
        assert str(items["child"].id) in union_ids
        assert str(items["custom"].id) in union_ids
        assert str(items["other"].id) not in union_ids

        superuser_response = client.get(
            f"{settings.API_V1_STR}/items/{items['other'].id}",
            headers=superuser_token_headers,
        )
        assert superuser_response.status_code == 200
    finally:
        for user in owners.values():
            db.delete(user)
        db.commit()
        for test_role in db.exec(
            select(Role).where(col(Role.code).in_({role.code, f"scope-union-{suffix}"}))
        ).all():
            db.delete(test_role)
        db.commit()
        for department in [child, custom, other, root]:
            db.exec(delete(Department).where(Department.id == department.id))
            db.commit()
