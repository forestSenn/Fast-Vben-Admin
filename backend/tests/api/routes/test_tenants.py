from io import BytesIO

from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from app.core.config import settings
from app.core.tenancy import DEFAULT_TENANT_ID
from app.models import (
    Department,
    DictionaryType,
    FileAsset,
    FileStorageChannel,
    MailAccount,
    Menu,
    Post,
    Role,
    RoleMenu,
    SiteMessageTemplate,
    SmsChannel,
    SystemSetting,
    Tenant,
    TenantInitializationTemplate,
    TenantMembership,
    TenantPlan,
    UserRole,
    UserSession,
)
from app.storage import delete_stored_file
from tests.utils.utils import get_superuser_token_headers, random_lower_string


def test_superuser_can_create_switch_and_archive_tenant(
    client: TestClient,
    db: Session,
) -> None:
    headers = get_superuser_token_headers(client)
    code = f"tenant-{random_lower_string()}"
    create_response = client.post(
        f"{settings.API_V1_STR}/tenants",
        headers=headers,
        json={"code": code, "name": "Tenant lifecycle test"},
    )
    assert create_response.status_code == 200
    tenant_id = create_response.json()["id"]

    try:
        tenant_uuid = create_response.json()["id"]
        tenant = db.get(Tenant, tenant_uuid)
        assert tenant is not None
        role_codes = set(
            db.exec(select(Role.code).where(Role.tenant_id == tenant.id)).all()
        )
        assert role_codes == {"admin", "super_admin", "user"}

        my_tenants_response = client.get(
            f"{settings.API_V1_STR}/tenants/me",
            headers=headers,
        )
        assert my_tenants_response.status_code == 200
        assert tenant_id in {
            item["tenant"]["id"] for item in my_tenants_response.json()
        }
        current_memberships = [
            item for item in my_tenants_response.json() if item["is_current"]
        ]
        assert len(current_memberships) == 1
        assert current_memberships[0]["tenant"]["id"] == str(DEFAULT_TENANT_ID)

        switch_response = client.post(
            f"{settings.API_V1_STR}/tenants/switch",
            headers=headers,
            json={"tenant_id": tenant_id},
        )
        assert switch_response.status_code == 200
        assert switch_response.json()["tenant_id"] == tenant_id
        tenant_headers = {
            "Authorization": f"Bearer {switch_response.json()['access_token']}"
        }
        assert (
            client.get(f"{settings.API_V1_STR}/users/me", headers=headers).status_code
            == 403
        )
        assert (
            client.get(
                f"{settings.API_V1_STR}/users/me", headers=tenant_headers
            ).status_code
            == 200
        )
        switched_memberships_response = client.get(
            f"{settings.API_V1_STR}/tenants/me",
            headers=tenant_headers,
        )
        assert switched_memberships_response.status_code == 200
        switched_memberships = switched_memberships_response.json()
        assert (
            next(item for item in switched_memberships if item["is_current"])["tenant"][
                "id"
            ]
            == tenant_id
        )

        tenant_roles_response = client.get(
            f"{settings.API_V1_STR}/roles",
            headers=tenant_headers,
        )
        assert tenant_roles_response.status_code == 200
        assert {role["code"] for role in tenant_roles_response.json()["items"]} == {
            "admin",
            "super_admin",
            "user",
        }
        platform_menu = db.exec(
            select(Menu).where(Menu.permission_code == "platform:tenant:list")
        ).one()
        tenant_admin_role_ids = db.exec(
            select(Role.id).where(
                Role.tenant_id == tenant.id,
                Role.code.in_(["admin", "super_admin"]),
            )
        ).all()
        assert not db.exec(
            select(RoleMenu).where(
                RoleMenu.role_id.in_(tenant_admin_role_ids),
                RoleMenu.menu_id == platform_menu.id,
            )
        ).first()

        switch_back_response = client.post(
            f"{settings.API_V1_STR}/tenants/switch",
            headers=tenant_headers,
            json={"tenant_id": str(DEFAULT_TENANT_ID)},
        )
        assert switch_back_response.status_code == 200
        default_headers = {
            "Authorization": f"Bearer {switch_back_response.json()['access_token']}"
        }
        archive_response = client.delete(
            f"{settings.API_V1_STR}/tenants/{tenant_id}",
            headers=default_headers,
        )
        assert archive_response.status_code == 204

        rejected_switch = client.post(
            f"{settings.API_V1_STR}/tenants/switch",
            headers=default_headers,
            json={"tenant_id": tenant_id},
        )
        assert rejected_switch.status_code == 403
        assert rejected_switch.json()["code"] == "TENANT_MEMBERSHIP_REQUIRED"
    finally:
        tenant = db.exec(select(Tenant).where(Tenant.code == code)).first()
        if tenant is not None:
            db.exec(delete(UserSession).where(UserSession.tenant_id == tenant.id))
            db.exec(delete(UserRole).where(UserRole.tenant_id == tenant.id))
            db.exec(
                delete(TenantMembership).where(TenantMembership.tenant_id == tenant.id)
            )
            roles = db.exec(select(Role).where(Role.tenant_id == tenant.id)).all()
            for role in roles:
                db.delete(role)
            db.commit()
            db.delete(tenant)
            db.commit()


def test_normal_user_cannot_manage_tenants(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    list_response = client.get(
        f"{settings.API_V1_STR}/tenants",
        headers=normal_user_token_headers,
    )
    create_response = client.post(
        f"{settings.API_V1_STR}/tenants",
        headers=normal_user_token_headers,
        json={"code": f"denied-{random_lower_string()}", "name": "Denied"},
    )
    assert list_response.status_code == 403
    assert create_response.status_code == 403


def test_default_tenant_cannot_be_disabled(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = client.patch(
        f"{settings.API_V1_STR}/tenants/{DEFAULT_TENANT_ID}",
        headers=superuser_token_headers,
        json={"is_active": False},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "TENANT_DEFAULT_PROTECTED"


def test_tenant_initialization_template_controls_seed_data(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    suffix = random_lower_string()[:10]
    template_id: str | None = None
    tenant_id: str | None = None
    template_code = f"minimal-{suffix}"
    tenant_code = f"templated-{suffix}"

    try:
        template_response = client.post(
            f"{settings.API_V1_STR}/tenants/templates",
            headers=superuser_token_headers,
            json={
                "code": template_code,
                "name": "Minimal test template",
                "root_department_code": "root",
                "root_department_name": "Root Department",
                "seed_posts": False,
                "seed_dictionaries": False,
                "seed_settings": False,
                "seed_storage_channels": False,
                "seed_message_templates": False,
                "seed_sms_channels": False,
                "seed_mail_accounts": False,
                "is_default": False,
                "is_active": True,
            },
        )
        assert template_response.status_code == 200
        template_id = template_response.json()["id"]

        tenant_response = client.post(
            f"{settings.API_V1_STR}/tenants",
            headers=superuser_token_headers,
            json={
                "code": tenant_code,
                "name": "Templated tenant",
                "initialization_template_id": template_id,
            },
        )
        assert tenant_response.status_code == 200
        tenant_id = tenant_response.json()["id"]
        assert tenant_response.json()["initialization_template_id"] == template_id
        assert (
            tenant_response.json()["initialization_template_name"]
            == "Minimal test template"
        )

        tenant = db.get(Tenant, tenant_id)
        assert tenant is not None
        departments = db.exec(
            select(Department).where(Department.tenant_id == tenant.id)
        ).all()
        assert [(department.code, department.name) for department in departments] == [
            ("root", "Root Department")
        ]
        assert set(
            db.exec(select(Role.code).where(Role.tenant_id == tenant.id)).all()
        ) == {"admin", "super_admin", "user"}
        for model in (
            Post,
            DictionaryType,
            SystemSetting,
            FileStorageChannel,
            SiteMessageTemplate,
            SmsChannel,
            MailAccount,
        ):
            assert not db.exec(
                select(model).where(model.tenant_id == tenant.id)
            ).first()

        in_use_response = client.delete(
            f"{settings.API_V1_STR}/tenants/templates/{template_id}",
            headers=superuser_token_headers,
        )
        assert in_use_response.status_code == 400
    finally:
        db.rollback()
        if tenant_id is not None:
            tenant = db.get(Tenant, tenant_id)
            if tenant is not None:
                db.exec(delete(UserSession).where(UserSession.tenant_id == tenant.id))
                db.exec(delete(UserRole).where(UserRole.tenant_id == tenant.id))
                db.exec(
                    delete(TenantMembership).where(
                        TenantMembership.tenant_id == tenant.id
                    )
                )
                for role in db.exec(
                    select(Role).where(Role.tenant_id == tenant.id)
                ).all():
                    db.delete(role)
                db.commit()
                db.delete(tenant)
                db.commit()

    assert template_id is not None
    disable_response = client.patch(
        f"{settings.API_V1_STR}/tenants/templates/{template_id}",
        headers=superuser_token_headers,
        json={"is_active": False},
    )
    assert disable_response.status_code == 200
    rejected_tenant = client.post(
        f"{settings.API_V1_STR}/tenants",
        headers=superuser_token_headers,
        json={
            "code": f"rejected-{suffix}",
            "name": "Rejected templated tenant",
            "initialization_template_id": template_id,
        },
    )
    assert rejected_tenant.status_code == 400
    assert (
        client.delete(
            f"{settings.API_V1_STR}/tenants/templates/{template_id}",
            headers=superuser_token_headers,
        ).status_code
        == 204
    )

    default_template = db.exec(
        select(TenantInitializationTemplate).where(
            TenantInitializationTemplate.is_default
        )
    ).one()
    assert (
        client.delete(
            f"{settings.API_V1_STR}/tenants/templates/{default_template.id}",
            headers=superuser_token_headers,
        ).status_code
        == 400
    )


def test_tenant_plan_quotas_are_enforced(
    client: TestClient,
    db: Session,
) -> None:
    headers = get_superuser_token_headers(client)
    suffix = random_lower_string()[:10]
    plan_id: str | None = None
    tenant_id: str | None = None
    file_id: str | None = None

    try:
        plan_response = client.post(
            f"{settings.API_V1_STR}/tenants/plans",
            headers=headers,
            json={
                "code": f"limited-{suffix}",
                "name": "Limited test plan",
                "max_members": 1,
                "max_file_assets": 1,
                "max_storage_bytes": 5,
                "is_active": True,
                "is_default": False,
            },
        )
        assert plan_response.status_code == 200
        plan_id = plan_response.json()["id"]

        tenant_response = client.post(
            f"{settings.API_V1_STR}/tenants",
            headers=headers,
            json={
                "code": f"quota-{suffix}",
                "name": "Quota test tenant",
                "plan_id": plan_id,
            },
        )
        assert tenant_response.status_code == 200
        tenant_id = tenant_response.json()["id"]
        assert tenant_response.json()["plan_id"] == plan_id

        assert (
            client.delete(
                f"{settings.API_V1_STR}/tenants/plans/{plan_id}",
                headers=headers,
            ).status_code
            == 400
        )

        switch_response = client.post(
            f"{settings.API_V1_STR}/tenants/switch",
            headers=headers,
            json={"tenant_id": tenant_id},
        )
        assert switch_response.status_code == 200
        tenant_headers = {
            "Authorization": f"Bearer {switch_response.json()['access_token']}"
        }

        member_response = client.post(
            f"{settings.API_V1_STR}/users",
            headers=tenant_headers,
            json={
                "email": f"quota-{suffix}@example.com",
                "password": "changethis",
            },
        )
        assert member_response.status_code == 409
        assert member_response.json()["code"] == "TENANT_MEMBER_QUOTA_EXCEEDED"

        upload_response = client.post(
            f"{settings.API_V1_STR}/files/upload",
            headers=tenant_headers,
            files={"file": ("quota.txt", BytesIO(b"12345"), "text/plain")},
        )
        assert upload_response.status_code == 200
        file_id = upload_response.json()["id"]

        file_count_response = client.post(
            f"{settings.API_V1_STR}/files/upload",
            headers=tenant_headers,
            files={"file": ("extra.txt", BytesIO(b"1"), "text/plain")},
        )
        assert file_count_response.status_code == 409
        assert file_count_response.json()["code"] == "TENANT_FILE_QUOTA_EXCEEDED"

        update_plan_response = client.patch(
            f"{settings.API_V1_STR}/tenants/plans/{plan_id}",
            headers=tenant_headers,
            json={"max_file_assets": 2},
        )
        assert update_plan_response.status_code == 200
        storage_response = client.post(
            f"{settings.API_V1_STR}/files/upload",
            headers=tenant_headers,
            files={"file": ("storage.txt", BytesIO(b"1"), "text/plain")},
        )
        assert storage_response.status_code == 409
        assert storage_response.json()["code"] == "TENANT_STORAGE_QUOTA_EXCEEDED"

        usage_response = client.get(
            f"{settings.API_V1_STR}/tenants/{tenant_id}/usage",
            headers=tenant_headers,
        )
        assert usage_response.status_code == 200
        usage = usage_response.json()
        assert usage["members"] == 1
        assert usage["file_assets"] == 1
        assert usage["storage_bytes"] == 5
        assert usage["plan"]["id"] == plan_id
    finally:
        db.rollback()
        if file_id is not None:
            file_asset = db.get(FileAsset, file_id)
            if file_asset is not None:
                delete_stored_file(
                    file_asset.storage_provider,
                    file_asset.storage_path,
                    db,
                    file_asset.tenant_id,
                )
                db.delete(file_asset)
                db.commit()
        if tenant_id is not None:
            tenant = db.get(Tenant, tenant_id)
            if tenant is not None:
                db.exec(delete(UserSession).where(UserSession.tenant_id == tenant.id))
                db.exec(delete(UserRole).where(UserRole.tenant_id == tenant.id))
                db.exec(
                    delete(TenantMembership).where(
                        TenantMembership.tenant_id == tenant.id
                    )
                )
                for role in db.exec(
                    select(Role).where(Role.tenant_id == tenant.id)
                ).all():
                    db.delete(role)
                db.commit()
                db.delete(tenant)
                db.commit()
        if plan_id is not None:
            plan = db.get(TenantPlan, plan_id)
            if plan is not None:
                db.delete(plan)
                db.commit()
