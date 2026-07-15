from io import BytesIO

from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, delete, select

from app import crud
from app.core.config import settings
from app.core.tenancy import DEFAULT_TENANT_ID
from app.models import (
    FileAsset,
    MailAccount,
    Notice,
    Role,
    SmsChannel,
    Tenant,
    TenantMembership,
    UserCreate,
    UserMessage,
    UserPost,
    UserRole,
    UserSession,
)
from app.storage import delete_stored_file
from tests.utils.utils import (
    get_superuser_token_headers,
    random_email,
    random_lower_string,
)


def test_users_and_roles_are_isolated_between_tenants(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    role_code = f"shared_{random_lower_string()}"
    default_role_response = client.post(
        f"{settings.API_V1_STR}/roles",
        headers=superuser_token_headers,
        json={"code": role_code, "name": "Default tenant role"},
    )
    assert default_role_response.status_code == 200
    default_role_id = default_role_response.json()["id"]

    tenant = Tenant(
        code=f"tenant-{random_lower_string()}",
        name="Cross-tenant security test",
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    tenant_role = Role(
        tenant_id=tenant.id,
        code=role_code,
        name="Other tenant role",
    )
    db.add(tenant_role)
    db.commit()
    db.refresh(tenant_role)
    tenant_user = crud.create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password=random_lower_string()),
        tenant_id=tenant.id,
    )
    default_user = crud.create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password=random_lower_string()),
    )

    try:
        roles_response = client.get(
            f"{settings.API_V1_STR}/roles",
            headers=superuser_token_headers,
        )
        assert roles_response.status_code == 200
        assert str(tenant_role.id) not in {
            role["id"] for role in roles_response.json()["items"]
        }
        assert (
            client.get(
                f"{settings.API_V1_STR}/roles/{tenant_role.id}",
                headers=superuser_token_headers,
            ).status_code
            == 404
        )

        users_response = client.get(
            f"{settings.API_V1_STR}/users",
            headers=superuser_token_headers,
        )
        assert users_response.status_code == 200
        assert tenant_user.email not in {
            user["email"] for user in users_response.json()["items"]
        }
        assert (
            client.get(
                f"{settings.API_V1_STR}/users/{tenant_user.id}",
                headers=superuser_token_headers,
            ).status_code
            == 404
        )
        assert (
            client.patch(
                f"{settings.API_V1_STR}/users/{tenant_user.id}",
                headers=superuser_token_headers,
                json={"full_name": "cross-tenant update"},
            ).status_code
            == 404
        )

        assignment_response = client.put(
            f"{settings.API_V1_STR}/users/{default_user.id}/roles",
            headers=superuser_token_headers,
            json={"role_ids": [str(tenant_role.id)]},
        )
        assert assignment_response.status_code == 400

        db.add(
            UserRole(
                user_id=default_user.id,
                role_id=tenant_role.id,
                tenant_id=tenant.id,
            )
        )
        try:
            db.commit()
            raise AssertionError("Cross-tenant role binding unexpectedly succeeded")
        except IntegrityError:
            db.rollback()
    finally:
        db.delete(default_user)
        db.delete(tenant_user)
        db.commit()
        db.delete(tenant_role)
        db.commit()
        db.delete(tenant)
        db.commit()
        delete_default_role = client.delete(
            f"{settings.API_V1_STR}/roles/{default_role_id}",
            headers=superuser_token_headers,
        )
        assert delete_default_role.status_code == 204


def test_organization_resources_are_isolated_between_tenants(
    client: TestClient,
    db: Session,
) -> None:
    default_headers = get_superuser_token_headers(client)
    current_user = client.get(
        f"{settings.API_V1_STR}/users/me", headers=default_headers
    ).json()
    shared_department_code = f"dept_{random_lower_string()}"
    shared_post_code = f"post_{random_lower_string()}"
    tenant_code = f"tenant-{random_lower_string()}"
    default_department_id: str | None = None
    default_post_id: str | None = None
    tenant_id: str | None = None

    try:
        default_department_response = client.post(
            f"{settings.API_V1_STR}/departments",
            headers=default_headers,
            json={"code": shared_department_code, "name": "Default department"},
        )
        assert default_department_response.status_code == 200
        default_department_id = default_department_response.json()["id"]
        default_post_response = client.post(
            f"{settings.API_V1_STR}/posts",
            headers=default_headers,
            json={"code": shared_post_code, "name": "Default post"},
        )
        assert default_post_response.status_code == 200
        default_post_id = default_post_response.json()["id"]

        tenant_response = client.post(
            f"{settings.API_V1_STR}/tenants",
            headers=default_headers,
            json={"code": tenant_code, "name": "Organization isolation tenant"},
        )
        assert tenant_response.status_code == 200
        tenant_id = tenant_response.json()["id"]
        switch_response = client.post(
            f"{settings.API_V1_STR}/tenants/switch",
            headers=default_headers,
            json={"tenant_id": tenant_id},
        )
        assert switch_response.status_code == 200
        tenant_headers = {
            "Authorization": f"Bearer {switch_response.json()['access_token']}"
        }

        tenant_department_response = client.post(
            f"{settings.API_V1_STR}/departments",
            headers=tenant_headers,
            json={"code": shared_department_code, "name": "Tenant department"},
        )
        assert tenant_department_response.status_code == 200
        tenant_department_id = tenant_department_response.json()["id"]
        tenant_post_response = client.post(
            f"{settings.API_V1_STR}/posts",
            headers=tenant_headers,
            json={"code": shared_post_code, "name": "Tenant post"},
        )
        assert tenant_post_response.status_code == 200
        tenant_post_id = tenant_post_response.json()["id"]

        departments_response = client.get(
            f"{settings.API_V1_STR}/departments",
            headers=tenant_headers,
            params={"keyword": shared_department_code},
        )
        assert departments_response.status_code == 200
        assert {item["id"] for item in departments_response.json()["items"]} == {
            tenant_department_id
        }
        posts_response = client.get(
            f"{settings.API_V1_STR}/posts",
            headers=tenant_headers,
            params={"keyword": shared_post_code},
        )
        assert posts_response.status_code == 200
        assert {item["id"] for item in posts_response.json()["items"]} == {
            tenant_post_id
        }

        assert (
            client.patch(
                f"{settings.API_V1_STR}/departments/{default_department_id}",
                headers=tenant_headers,
                json={"name": "Cross-tenant update"},
            ).status_code
            == 404
        )
        assert (
            client.patch(
                f"{settings.API_V1_STR}/posts/{default_post_id}",
                headers=tenant_headers,
                json={"name": "Cross-tenant update"},
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"{settings.API_V1_STR}/departments",
                headers=tenant_headers,
                json={
                    "code": f"child_{random_lower_string()}",
                    "name": "Cross-tenant child",
                    "parent_id": default_department_id,
                },
            ).status_code
            == 404
        )

        update_user_response = client.patch(
            f"{settings.API_V1_STR}/users/{current_user['id']}",
            headers=tenant_headers,
            json={"department_id": tenant_department_id},
        )
        assert update_user_response.status_code == 200
        assert update_user_response.json()["department_id"] == tenant_department_id
        assert (
            client.put(
                f"{settings.API_V1_STR}/users/{current_user['id']}/posts",
                headers=tenant_headers,
                json={"post_ids": [default_post_id]},
            ).status_code
            == 400
        )

        db.add(
            UserPost(
                user_id=current_user["id"],
                post_id=default_post_id,
                tenant_id=tenant_id,
            )
        )
        try:
            db.commit()
            raise AssertionError("Cross-tenant post binding unexpectedly succeeded")
        except IntegrityError:
            db.rollback()

        switch_back_response = client.post(
            f"{settings.API_V1_STR}/tenants/switch",
            headers=tenant_headers,
            json={"tenant_id": str(DEFAULT_TENANT_ID)},
        )
        assert switch_back_response.status_code == 200
        default_headers = {
            "Authorization": f"Bearer {switch_back_response.json()['access_token']}"
        }
        default_user_response = client.get(
            f"{settings.API_V1_STR}/users/me", headers=default_headers
        )
        assert default_user_response.status_code == 200
        assert default_user_response.json()["department_id"] != tenant_department_id
    finally:
        default_headers = get_superuser_token_headers(client)
        if default_post_id is not None:
            client.delete(
                f"{settings.API_V1_STR}/posts/{default_post_id}",
                headers=default_headers,
            )
        if default_department_id is not None:
            client.delete(
                f"{settings.API_V1_STR}/departments/{default_department_id}",
                headers=default_headers,
            )
        if tenant_id is not None:
            tenant = db.get(Tenant, tenant_id)
            if tenant is not None:
                db.exec(delete(UserSession).where(UserSession.tenant_id == tenant.id))
                db.exec(delete(UserPost).where(UserPost.tenant_id == tenant.id))
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


def test_files_messages_channels_and_logs_are_isolated_between_tenants(
    client: TestClient,
    db: Session,
) -> None:
    default_headers = get_superuser_token_headers(client)
    suffix = random_lower_string()[:10]
    tenant_id: str | None = None
    file_ids: list[str] = []
    notice_ids: list[str] = []
    sms_channel_ids: list[str] = []
    mail_account_ids: list[str] = []

    try:
        default_file_response = client.post(
            f"{settings.API_V1_STR}/files/upload",
            headers=default_headers,
            files={
                "file": (
                    f"default-{suffix}.txt",
                    BytesIO(b"default tenant"),
                    "text/plain",
                )
            },
        )
        assert default_file_response.status_code == 200
        default_file = default_file_response.json()
        file_ids.append(default_file["id"])
        assert default_file["tenant_id"] == str(DEFAULT_TENANT_ID)
        assert f"tenants/{DEFAULT_TENANT_ID}/" in default_file["storage_path"]

        default_notice_response = client.post(
            f"{settings.API_V1_STR}/notices",
            headers=default_headers,
            json={
                "title": f"Default notice {suffix}",
                "content": "Default tenant notice",
            },
        )
        assert default_notice_response.status_code == 200
        default_notice_id = default_notice_response.json()["id"]
        notice_ids.append(default_notice_id)
        assert (
            client.post(
                f"{settings.API_V1_STR}/notices/{default_notice_id}/publish",
                headers=default_headers,
            ).status_code
            == 200
        )

        shared_sms_code = f"shared-sms-{suffix}"
        default_sms_response = client.post(
            f"{settings.API_V1_STR}/sms/channels",
            headers=default_headers,
            json={
                "name": "Default SMS channel",
                "code": shared_sms_code,
                "provider": "debug",
                "signature": "Default",
            },
        )
        assert default_sms_response.status_code == 200
        default_sms_id = default_sms_response.json()["id"]
        sms_channel_ids.append(default_sms_id)

        shared_mail_code = f"shared-mail-{suffix}"
        mail_payload = {
            "name": "Shared mail account",
            "code": shared_mail_code,
            "email": f"sender-{suffix}@example.com",
            "host": "smtp.example.com",
            "port": 465,
            "ssl_enable": True,
            "starttls_enable": False,
        }
        default_mail_response = client.post(
            f"{settings.API_V1_STR}/mail/accounts",
            headers=default_headers,
            json=mail_payload,
        )
        assert default_mail_response.status_code == 200
        default_mail_id = default_mail_response.json()["id"]
        mail_account_ids.append(default_mail_id)

        tenant_response = client.post(
            f"{settings.API_V1_STR}/tenants",
            headers=default_headers,
            json={
                "code": f"resources-{suffix}",
                "name": "Resource isolation tenant",
            },
        )
        assert tenant_response.status_code == 200
        tenant_id = tenant_response.json()["id"]
        switch_response = client.post(
            f"{settings.API_V1_STR}/tenants/switch",
            headers=default_headers,
            json={"tenant_id": tenant_id},
        )
        assert switch_response.status_code == 200
        tenant_headers = {
            "Authorization": f"Bearer {switch_response.json()['access_token']}"
        }

        tenant_file_response = client.post(
            f"{settings.API_V1_STR}/files/upload",
            headers=tenant_headers,
            files={
                "file": (
                    f"tenant-{suffix}.txt",
                    BytesIO(b"other tenant"),
                    "text/plain",
                )
            },
        )
        assert tenant_file_response.status_code == 200
        tenant_file = tenant_file_response.json()
        file_ids.append(tenant_file["id"])
        assert tenant_file["tenant_id"] == tenant_id
        assert f"tenants/{tenant_id}/" in tenant_file["storage_path"]

        files_response = client.get(
            f"{settings.API_V1_STR}/files",
            headers=tenant_headers,
            params={"keyword": suffix},
        )
        assert files_response.status_code == 200
        assert {item["id"] for item in files_response.json()["items"]} == {
            tenant_file["id"]
        }
        assert (
            client.get(
                f"{settings.API_V1_STR}/files/{default_file['id']}",
                headers=tenant_headers,
            ).status_code
            == 404
        )
        assert (
            client.get(
                f"{settings.API_V1_STR}/files/{default_file['id']}/download",
                headers=tenant_headers,
            ).status_code
            == 403
        )

        tenant_notice_response = client.post(
            f"{settings.API_V1_STR}/notices",
            headers=tenant_headers,
            json={
                "title": f"Tenant notice {suffix}",
                "content": "Tenant-only notice",
            },
        )
        assert tenant_notice_response.status_code == 200
        tenant_notice_id = tenant_notice_response.json()["id"]
        notice_ids.append(tenant_notice_id)
        assert (
            client.post(
                f"{settings.API_V1_STR}/notices/{tenant_notice_id}/publish",
                headers=tenant_headers,
            ).status_code
            == 200
        )
        assert (
            client.patch(
                f"{settings.API_V1_STR}/notices/{default_notice_id}",
                headers=tenant_headers,
                json={"title": "Cross-tenant update"},
            ).status_code
            == 404
        )
        messages_response = client.get(
            f"{settings.API_V1_STR}/messages/me",
            headers=tenant_headers,
        )
        assert messages_response.status_code == 200
        assert tenant_notice_id in {
            item["notice_id"] for item in messages_response.json()["items"]
        }
        assert default_notice_id not in {
            item["notice_id"] for item in messages_response.json()["items"]
        }

        tenant_sms_response = client.post(
            f"{settings.API_V1_STR}/sms/channels",
            headers=tenant_headers,
            json={
                "name": "Tenant SMS channel",
                "code": shared_sms_code,
                "provider": "debug",
                "signature": "Tenant",
            },
        )
        assert tenant_sms_response.status_code == 200
        tenant_sms_id = tenant_sms_response.json()["id"]
        sms_channel_ids.append(tenant_sms_id)
        assert tenant_sms_response.json()["tenant_id"] == tenant_id
        assert (
            client.patch(
                f"{settings.API_V1_STR}/sms/channels/{default_sms_id}",
                headers=tenant_headers,
                json={"name": "Cross-tenant update"},
            ).status_code
            == 404
        )

        tenant_mail_response = client.post(
            f"{settings.API_V1_STR}/mail/accounts",
            headers=tenant_headers,
            json={**mail_payload, "name": "Tenant mail account"},
        )
        assert tenant_mail_response.status_code == 200
        tenant_mail_id = tenant_mail_response.json()["id"]
        mail_account_ids.append(tenant_mail_id)
        assert tenant_mail_response.json()["tenant_id"] == tenant_id
        assert (
            client.patch(
                f"{settings.API_V1_STR}/mail/accounts/{default_mail_id}",
                headers=tenant_headers,
                json={"name": "Cross-tenant update"},
            ).status_code
            == 404
        )

        storage_response = client.get(
            f"{settings.API_V1_STR}/files/storage-channels",
            headers=tenant_headers,
            params={"keyword": "local"},
        )
        assert storage_response.status_code == 200
        assert storage_response.json()["items"]
        assert all(
            item["tenant_id"] == tenant_id for item in storage_response.json()["items"]
        )
        operation_logs_response = client.get(
            f"{settings.API_V1_STR}/logs/operation",
            headers=tenant_headers,
            params={"keyword": "/api/v1/", "page_size": 100},
        )
        assert operation_logs_response.status_code == 200
        assert operation_logs_response.json()["items"]
        assert all(
            item["tenant_id"] == tenant_id
            for item in operation_logs_response.json()["items"]
        )
    finally:
        db.rollback()
        db.expire_all()
        for file_id in file_ids:
            file_asset = db.get(FileAsset, file_id)
            if file_asset is not None:
                delete_stored_file(
                    file_asset.storage_provider,
                    file_asset.storage_path,
                    db,
                    file_asset.tenant_id,
                )
                db.delete(file_asset)
        if notice_ids:
            db.exec(delete(UserMessage).where(UserMessage.notice_id.in_(notice_ids)))
            db.exec(delete(Notice).where(Notice.id.in_(notice_ids)))
        if sms_channel_ids:
            db.exec(delete(SmsChannel).where(SmsChannel.id.in_(sms_channel_ids)))
        if mail_account_ids:
            db.exec(delete(MailAccount).where(MailAccount.id.in_(mail_account_ids)))
        db.commit()
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
