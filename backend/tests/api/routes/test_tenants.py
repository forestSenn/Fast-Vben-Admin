from datetime import UTC, datetime, timedelta
from io import BytesIO

from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from app.api.routes import tenants as tenant_routes
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
    TenantLifecycleStatus,
    TenantMembership,
    TenantPlan,
    TenantPlanMenu,
    TenantProfile,
    User,
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
    denied_responses = [
        list_response,
        create_response,
        client.get(
            f"{settings.API_V1_STR}/tenants/plans",
            headers=normal_user_token_headers,
        ),
        client.put(
            f"{settings.API_V1_STR}/tenants/plans/{DEFAULT_TENANT_ID}/menus",
            headers=normal_user_token_headers,
            json={"menu_ids": []},
        ),
        client.post(
            f"{settings.API_V1_STR}/tenants/{DEFAULT_TENANT_ID}/lifecycle",
            headers=normal_user_token_headers,
            json={"action": "freeze", "frozen_reason": "Denied"},
        ),
        client.post(
            f"{settings.API_V1_STR}/tenants/{DEFAULT_TENANT_ID}/sync-menus",
            headers=normal_user_token_headers,
        ),
        client.get(
            f"{settings.API_V1_STR}/tenants/templates",
            headers=normal_user_token_headers,
        ),
    ]
    assert all(response.status_code == 403 for response in denied_responses)


def test_default_tenant_cannot_be_modified(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    responses = [
        client.patch(
            f"{settings.API_V1_STR}/tenants/{DEFAULT_TENANT_ID}",
            headers=superuser_token_headers,
            json={"name": "Changed default tenant"},
        ),
        client.post(
            f"{settings.API_V1_STR}/tenants/{DEFAULT_TENANT_ID}/lifecycle",
            headers=superuser_token_headers,
            json={"action": "freeze", "frozen_reason": "Protected"},
        ),
        client.post(
            f"{settings.API_V1_STR}/tenants/{DEFAULT_TENANT_ID}/sync-menus",
            headers=superuser_token_headers,
        ),
        client.delete(
            f"{settings.API_V1_STR}/tenants/{DEFAULT_TENANT_ID}",
            headers=superuser_token_headers,
        ),
    ]

    assert all(response.status_code == 400 for response in responses)
    assert all(
        response.json()["code"] == "TENANT_DEFAULT_PROTECTED" for response in responses
    )


def test_default_plan_cannot_be_modified(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    default_plan = db.exec(select(TenantPlan).where(TenantPlan.is_default)).one()
    responses = [
        client.patch(
            f"{settings.API_V1_STR}/tenants/plans/{default_plan.id}",
            headers=superuser_token_headers,
            json={"name": "Changed default plan"},
        ),
        client.put(
            f"{settings.API_V1_STR}/tenants/plans/{default_plan.id}/menus",
            headers=superuser_token_headers,
            json={"menu_ids": []},
        ),
        client.delete(
            f"{settings.API_V1_STR}/tenants/plans/{default_plan.id}",
            headers=superuser_token_headers,
        ),
    ]

    assert all(response.status_code == 400 for response in responses)
    assert all(
        response.json()["code"] == "TENANT_DEFAULT_PLAN_PROTECTED"
        for response in responses
    )

    sync_response = client.post(
        f"{settings.API_V1_STR}/tenants/plans/{default_plan.id}/sync-menus",
        headers=superuser_token_headers,
    )
    assert sync_response.status_code == 200
    assert sync_response.json()["success_count"] >= 1


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


def test_tenant_operations_lifecycle_and_administrator_provisioning(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    suffix = random_lower_string()[:10]
    tenant_code = f"ops-{suffix}"
    administrator_email = f"ops-admin-{suffix}@example.com"
    administrator_password = "tenant-admin-password"
    now = datetime.now(UTC)

    try:
        create_response = client.post(
            f"{settings.API_V1_STR}/tenants",
            headers=superuser_token_headers,
            json={
                "code": tenant_code,
                "name": "Operations tenant",
                "contact_name": "Operations Contact",
                "contact_mobile": "13800138000",
                "industry": 10,
                "type": 2,
                "owner_name": "Customer Success A",
                "customer_source": "partner",
                "follow_up_notes": "Initial onboarding",
                "lifecycle_status": "trial",
                "effective_at": now.isoformat(),
                "trial_ends_at": (now + timedelta(days=14)).isoformat(),
                "service_expires_at": (now + timedelta(days=30)).isoformat(),
                "username": administrator_email,
                "password": administrator_password,
            },
        )
        assert create_response.status_code == 200
        tenant_data = create_response.json()
        tenant_id = tenant_data["id"]
        assert tenant_data["lifecycle_status"] == "trial"
        assert tenant_data["owner_name"] == "Customer Success A"
        assert tenant_data["contact_name"] == "Operations Contact"

        profile = db.get(TenantProfile, tenant_id)
        assert profile is not None
        assert profile.customer_source == "partner"
        administrator = db.exec(
            select(User).where(User.email == administrator_email)
        ).one()
        assert profile.contact_user_id == administrator.id
        membership = db.exec(
            select(TenantMembership).where(
                TenantMembership.user_id == administrator.id,
                TenantMembership.tenant_id == profile.tenant_id,
            )
        ).one()
        assert membership.is_active
        administrator_roles = set(
            db.exec(
                select(Role.code)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(
                    UserRole.user_id == administrator.id,
                    UserRole.tenant_id == profile.tenant_id,
                )
            ).all()
        )
        assert administrator_roles == {"super_admin"}

        list_response = client.get(
            f"{settings.API_V1_STR}/tenants",
            headers=superuser_token_headers,
            params={
                "keyword": "13800138000",
                "lifecycle_status": "trial",
                "expiring_in_days": 31,
            },
        )
        assert list_response.status_code == 200
        assert [item["id"] for item in list_response.json()["items"]] == [tenant_id]

        login_response = client.post(
            f"{settings.API_V1_STR}/login/access-token",
            data={
                "username": administrator_email,
                "password": administrator_password,
                "tenant_code": tenant_code,
            },
        )
        assert login_response.status_code == 200
        administrator_headers = {
            "Authorization": f"Bearer {login_response.json()['access_token']}"
        }

        formal_response = client.post(
            f"{settings.API_V1_STR}/tenants/{tenant_id}/lifecycle",
            headers=superuser_token_headers,
            json={"action": "convert_to_formal"},
        )
        assert formal_response.status_code == 200
        assert formal_response.json()["lifecycle_status"] == "formal"

        renewed_until = now + timedelta(days=365)
        renew_response = client.post(
            f"{settings.API_V1_STR}/tenants/{tenant_id}/lifecycle",
            headers=superuser_token_headers,
            json={
                "action": "renew",
                "service_expires_at": renewed_until.isoformat(),
            },
        )
        assert renew_response.status_code == 200

        freeze_response = client.post(
            f"{settings.API_V1_STR}/tenants/{tenant_id}/lifecycle",
            headers=superuser_token_headers,
            json={"action": "freeze", "frozen_reason": "Payment overdue"},
        )
        assert freeze_response.status_code == 200
        assert freeze_response.json()["lifecycle_status"] == "frozen"
        assert (
            client.get(
                f"{settings.API_V1_STR}/users/me", headers=administrator_headers
            ).status_code
            == 403
        )

        unfreeze_response = client.post(
            f"{settings.API_V1_STR}/tenants/{tenant_id}/lifecycle",
            headers=superuser_token_headers,
            json={"action": "unfreeze"},
        )
        assert unfreeze_response.status_code == 200
        assert unfreeze_response.json()["lifecycle_status"] == "formal"

        profile = db.get(TenantProfile, tenant_id)
        tenant = db.get(Tenant, tenant_id)
        assert profile is not None
        assert tenant is not None
        profile.service_expires_at = now - timedelta(minutes=1)
        tenant.is_active = True
        db.add(profile)
        db.add(tenant)
        db.commit()

        expired_login = client.post(
            f"{settings.API_V1_STR}/login/access-token",
            data={
                "username": administrator_email,
                "password": administrator_password,
                "tenant_code": tenant_code,
            },
        )
        assert expired_login.status_code == 403
        expired_list = client.get(
            f"{settings.API_V1_STR}/tenants",
            headers=superuser_token_headers,
            params={"lifecycle_status": "expired", "keyword": tenant_code},
        )
        assert expired_list.status_code == 200
        assert expired_list.json()["items"][0]["lifecycle_status"] == "expired"

        recover_response = client.post(
            f"{settings.API_V1_STR}/tenants/{tenant_id}/lifecycle",
            headers=superuser_token_headers,
            json={
                "action": "renew",
                "service_expires_at": renewed_until.isoformat(),
            },
        )
        assert recover_response.status_code == 200
        assert recover_response.json()["lifecycle_status"] == "formal"

        profile = db.get(TenantProfile, tenant_id)
        tenant = db.get(Tenant, tenant_id)
        assert profile is not None
        assert tenant is not None
        profile.lifecycle_status = TenantLifecycleStatus.FROZEN
        profile.lifecycle_status_before_freeze = TenantLifecycleStatus.TRIAL
        profile.trial_ends_at = now - timedelta(minutes=1)
        profile.service_expires_at = now - timedelta(minutes=1)
        tenant.is_active = False
        db.add(profile)
        db.add(tenant)
        db.commit()

        frozen_trial_renew = client.post(
            f"{settings.API_V1_STR}/tenants/{tenant_id}/lifecycle",
            headers=superuser_token_headers,
            json={
                "action": "renew",
                "service_expires_at": renewed_until.isoformat(),
            },
        )
        assert frozen_trial_renew.status_code == 200
        assert frozen_trial_renew.json()["lifecycle_status"] == "frozen"

        frozen_trial_unfreeze = client.post(
            f"{settings.API_V1_STR}/tenants/{tenant_id}/lifecycle",
            headers=superuser_token_headers,
            json={"action": "unfreeze"},
        )
        assert frozen_trial_unfreeze.status_code == 200
        assert frozen_trial_unfreeze.json()["lifecycle_status"] == "formal"
    finally:
        db.rollback()
        tenant = db.exec(select(Tenant).where(Tenant.code == tenant_code)).first()
        if tenant is not None:
            db.exec(delete(UserSession).where(UserSession.tenant_id == tenant.id))
            db.commit()
            db.delete(tenant)
            db.commit()
        administrator = db.exec(
            select(User).where(User.email == administrator_email)
        ).first()
        if administrator is not None:
            db.delete(administrator)
            db.commit()


def test_tenant_plan_menu_authorization_and_sync(
    client: TestClient,
    db: Session,
    monkeypatch,
    superuser_token_headers: dict[str, str],
) -> None:
    suffix = random_lower_string()[:10]
    plan_code = f"menu-plan-{suffix}"
    tenant_code = f"menu-tenant-{suffix}"

    try:
        plan_response = client.post(
            f"{settings.API_V1_STR}/tenants/plans",
            headers=superuser_token_headers,
            json={
                "code": plan_code,
                "name": "Menu authorization plan",
                "type": 2,
                "price": 199,
                "published": 1,
                "order_num": 20,
                "subscription_num": 99,
                "subscription_total_amount": 9999,
                "remark": "Menu sync test",
            },
        )
        assert plan_response.status_code == 200
        plan_data = plan_response.json()
        plan_id = plan_data["id"]
        assert plan_data["type"] == 2
        assert plan_data["price"] == 199
        assert plan_data["subscription_num"] == 0
        assert plan_data["subscription_total_amount"] == 0
        assert plan_data["menu_count"] > 0

        dashboard_menu = db.exec(
            select(Menu).where(Menu.permission_code == "dashboard:view")
        ).one()
        item_menu = db.exec(
            select(Menu).where(Menu.permission_code == "business:item:list")
        ).one()
        platform_menu = db.exec(
            select(Menu).where(Menu.permission_code == "platform:tenant:list")
        ).one()

        reject_platform = client.put(
            f"{settings.API_V1_STR}/tenants/plans/{plan_id}/menus",
            headers=superuser_token_headers,
            json={"menu_ids": [str(platform_menu.id)]},
        )
        assert reject_platform.status_code == 400

        grant_response = client.put(
            f"{settings.API_V1_STR}/tenants/plans/{plan_id}/menus",
            headers=superuser_token_headers,
            json={"menu_ids": [str(dashboard_menu.id), str(item_menu.id)]},
        )
        assert grant_response.status_code == 200
        granted_ids = set(grant_response.json())
        assert {str(dashboard_menu.id), str(item_menu.id)} <= granted_ids

        tenant_response = client.post(
            f"{settings.API_V1_STR}/tenants",
            headers=superuser_token_headers,
            json={
                "code": tenant_code,
                "name": "Menu authorization tenant",
                "plan_id": plan_id,
            },
        )
        assert tenant_response.status_code == 200
        tenant_id = tenant_response.json()["id"]
        roles = db.exec(select(Role).where(Role.tenant_id == tenant_id)).all()
        role_by_code = {role.code: role for role in roles}
        super_admin_menu_ids = set(
            db.exec(
                select(RoleMenu.menu_id).where(
                    RoleMenu.role_id == role_by_code["super_admin"].id
                )
            ).all()
        )
        assert super_admin_menu_ids == {dashboard_menu.id, item_menu.id}

        custom_role = Role(
            tenant_id=tenant_id,
            code="custom",
            name="Custom role",
            is_system=False,
        )
        db.add(custom_role)
        db.flush()
        db.add(RoleMenu(role_id=custom_role.id, menu_id=item_menu.id))
        db.commit()

        reduce_response = client.put(
            f"{settings.API_V1_STR}/tenants/plans/{plan_id}/menus",
            headers=superuser_token_headers,
            json={"menu_ids": [str(dashboard_menu.id)]},
        )
        assert reduce_response.status_code == 200
        sync_response = client.post(
            f"{settings.API_V1_STR}/tenants/plans/{plan_id}/sync-menus",
            headers=superuser_token_headers,
        )
        assert sync_response.status_code == 200
        assert sync_response.json()["success_count"] == 1
        assert sync_response.json()["failed_count"] == 0

        def fail_menu_sync(*, session: Session, tenant: Tenant) -> bool:
            del session, tenant
            raise RuntimeError("simulated menu sync failure")

        monkeypatch.setattr(
            tenant_routes,
            "sync_tenant_plan_role_menus",
            fail_menu_sync,
        )
        failed_sync_response = client.post(
            f"{settings.API_V1_STR}/tenants/plans/{plan_id}/sync-menus",
            headers=superuser_token_headers,
        )
        assert failed_sync_response.status_code == 200
        assert failed_sync_response.json() == {
            "success_count": 0,
            "failed_count": 1,
            "skipped_count": 0,
        }

        synced_super_admin_menu_ids = set(
            db.exec(
                select(RoleMenu.menu_id).where(
                    RoleMenu.role_id == role_by_code["super_admin"].id
                )
            ).all()
        )
        assert synced_super_admin_menu_ids == {dashboard_menu.id}
        assert db.exec(
            select(RoleMenu).where(
                RoleMenu.role_id == custom_role.id,
                RoleMenu.menu_id == item_menu.id,
            )
        ).one()

        stored_menu_ids = set(
            db.exec(
                select(TenantPlanMenu.menu_id).where(
                    TenantPlanMenu.plan_id == plan_id
                )
            ).all()
        )
        assert stored_menu_ids == {dashboard_menu.id}
    finally:
        db.rollback()
        tenant = db.exec(select(Tenant).where(Tenant.code == tenant_code)).first()
        if tenant is not None:
            db.exec(delete(UserSession).where(UserSession.tenant_id == tenant.id))
            db.commit()
            db.delete(tenant)
            db.commit()
        plan = db.exec(select(TenantPlan).where(TenantPlan.code == plan_code)).first()
        if plan is not None:
            db.delete(plan)
            db.commit()
