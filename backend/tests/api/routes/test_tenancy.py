import uuid
from base64 import urlsafe_b64encode
from hashlib import sha256
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
    OAuth2AccessToken,
    OAuth2AuthorizationCode,
    OAuth2Client,
    Role,
    SmsChannel,
    SocialClient,
    SocialUser,
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
        default_headers = get_superuser_token_headers(client)

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


def test_oauth2_and_social_resources_are_isolated_between_tenants(
    client: TestClient,
    db: Session,
) -> None:
    default_headers = get_superuser_token_headers(client)
    suffix = random_lower_string()[:10]
    verifier = "a" * 43
    challenge = (
        urlsafe_b64encode(sha256(verifier.encode()).digest()).decode().rstrip("=")
    )
    tenant_id: str | None = None
    oauth_client_ids: list[uuid.UUID] = []
    social_client_ids: list[uuid.UUID] = []
    social_user_ids: list[uuid.UUID] = []

    default_oauth_client_code = f"default-oauth-{suffix}"
    tenant_oauth_client_code = f"tenant-oauth-{suffix}"
    redirect_uri = f"https://client.example.test/{suffix}/callback"
    default_social_client_code = f"default-social-client-{suffix}"
    tenant_social_client_code = f"tenant-social-client-{suffix}"
    shared_social_openid = f"shared-openid-{suffix}"
    shared_social_type = f"tenant-social-{suffix[:6]}"
    shared_social_user_type = f"admin-{suffix[:6]}"

    try:
        default_oauth_client_response = client.post(
            f"{settings.API_V1_STR}/oauth2/clients",
            headers=default_headers,
            json={
                "client_id": default_oauth_client_code,
                "client_secret": "default-secret",
                "name": "Default OAuth2 client",
                "redirect_uris": redirect_uri,
            },
        )
        assert default_oauth_client_response.status_code == 200
        default_oauth_client_id = default_oauth_client_response.json()["id"]
        oauth_client_ids.append(uuid.UUID(default_oauth_client_id))
        assert (
            default_oauth_client_response.json()["tenant_id"] == str(DEFAULT_TENANT_ID)
        )

        default_social_client_response = client.post(
            f"{settings.API_V1_STR}/social/clients",
            headers=default_headers,
            json={
                "name": "Default social client",
                "social_type": shared_social_type,
                "user_type": shared_social_user_type,
                "client_id": default_social_client_code,
            },
        )
        assert default_social_client_response.status_code == 200
        default_social_client_id = default_social_client_response.json()["id"]
        social_client_ids.append(uuid.UUID(default_social_client_id))
        assert (
            default_social_client_response.json()["tenant_id"]
            == str(DEFAULT_TENANT_ID)
        )

        default_social_user = SocialUser(
            tenant_id=DEFAULT_TENANT_ID,
            type=shared_social_type,
            openid=shared_social_openid,
            social_client_id=uuid.UUID(default_social_client_id),
        )
        db.add(default_social_user)
        db.commit()
        db.refresh(default_social_user)
        social_user_ids.append(default_social_user.id)

        tenant_response = client.post(
            f"{settings.API_V1_STR}/tenants",
            headers=default_headers,
            json={
                "code": f"oauth-social-{suffix}",
                "name": "OAuth social isolation tenant",
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
        default_headers = get_superuser_token_headers(client)

        tenant_oauth_client_response = client.post(
            f"{settings.API_V1_STR}/oauth2/clients",
            headers=tenant_headers,
            json={
                "client_id": tenant_oauth_client_code,
                "client_secret": "tenant-secret",
                "name": "Tenant OAuth2 client",
                "redirect_uris": redirect_uri,
            },
        )
        assert tenant_oauth_client_response.status_code == 200
        tenant_oauth_client_id = tenant_oauth_client_response.json()["id"]
        oauth_client_ids.append(uuid.UUID(tenant_oauth_client_id))
        assert tenant_oauth_client_response.json()["tenant_id"] == tenant_id

        tenant_oauth_clients_response = client.get(
            f"{settings.API_V1_STR}/oauth2/clients",
            headers=tenant_headers,
            params={"keyword": suffix},
        )
        assert tenant_oauth_clients_response.status_code == 200
        assert {
            item["id"] for item in tenant_oauth_clients_response.json()["items"]
        } == {tenant_oauth_client_id}
        assert (
            client.patch(
                f"{settings.API_V1_STR}/oauth2/clients/{default_oauth_client_id}",
                headers=tenant_headers,
                json={"name": "Cross-tenant update"},
            ).status_code
            == 404
        )
        assert (
            client.get(
                f"{settings.API_V1_STR}/oauth2/authorize",
                headers=default_headers,
                params={
                    "client_id": tenant_oauth_client_code,
                    "redirect_uri": redirect_uri,
                    "code_challenge": challenge,
                },
            ).status_code
            == 400
        )

        authorized = client.get(
            f"{settings.API_V1_STR}/oauth2/authorize",
            headers=tenant_headers,
            follow_redirects=False,
            params={
                "approved": True,
                "client_id": tenant_oauth_client_code,
                "redirect_uri": redirect_uri,
                "code_challenge": challenge,
                "scope": "read",
            },
        )
        assert authorized.status_code == 302
        authorization_code = authorized.headers["location"].split("code=", 1)[1]
        token_response = client.post(
            f"{settings.API_V1_STR}/oauth2/token",
            data={
                "grant_type": "authorization_code",
                "client_id": tenant_oauth_client_code,
                "client_secret": "tenant-secret",
                "code": authorization_code,
                "redirect_uri": redirect_uri,
                "code_verifier": verifier,
            },
        )
        assert token_response.status_code == 200

        tenant_token_list_response = client.get(
            f"{settings.API_V1_STR}/oauth2/tokens",
            headers=tenant_headers,
            params={"client_id": tenant_oauth_client_code},
        )
        assert tenant_token_list_response.status_code == 200
        assert tenant_token_list_response.json()["items"]
        tenant_token_id = tenant_token_list_response.json()["items"][0]["id"]
        assert all(
            item["tenant_id"] == tenant_id
            for item in tenant_token_list_response.json()["items"]
        )
        default_token_list_response = client.get(
            f"{settings.API_V1_STR}/oauth2/tokens",
            headers=default_headers,
            params={"client_id": tenant_oauth_client_code},
        )
        assert default_token_list_response.status_code == 200
        assert default_token_list_response.json()["items"] == []
        assert (
            client.delete(
                f"{settings.API_V1_STR}/oauth2/tokens/{tenant_token_id}",
                headers=default_headers,
            ).status_code
            == 404
        )

        tenant_social_client_response = client.post(
            f"{settings.API_V1_STR}/social/clients",
            headers=tenant_headers,
            json={
                "name": "Tenant social client",
                "social_type": shared_social_type,
                "user_type": shared_social_user_type,
                "client_id": tenant_social_client_code,
            },
        )
        assert tenant_social_client_response.status_code == 200
        tenant_social_client_id = tenant_social_client_response.json()["id"]
        social_client_ids.append(uuid.UUID(tenant_social_client_id))
        assert tenant_social_client_response.json()["tenant_id"] == tenant_id

        tenant_social_user = SocialUser(
            tenant_id=uuid.UUID(tenant_id),
            type=shared_social_type,
            openid=shared_social_openid,
            social_client_id=uuid.UUID(tenant_social_client_id),
        )
        db.add(tenant_social_user)
        db.commit()
        db.refresh(tenant_social_user)
        social_user_ids.append(tenant_social_user.id)

        tenant_social_clients_response = client.get(
            f"{settings.API_V1_STR}/social/clients",
            headers=tenant_headers,
            params={"keyword": suffix},
        )
        assert tenant_social_clients_response.status_code == 200
        assert {
            item["id"] for item in tenant_social_clients_response.json()["items"]
        } == {tenant_social_client_id}
        assert (
            client.patch(
                f"{settings.API_V1_STR}/social/clients/{default_social_client_id}",
                headers=tenant_headers,
                json={"name": "Cross-tenant update"},
            ).status_code
            == 404
        )

        default_social_users_response = client.get(
            f"{settings.API_V1_STR}/social/users",
            headers=default_headers,
            params={"openid": shared_social_openid},
        )
        assert default_social_users_response.status_code == 200
        assert {item["id"] for item in default_social_users_response.json()["items"]} == {
            str(default_social_user.id)
        }
        tenant_social_users_response = client.get(
            f"{settings.API_V1_STR}/social/users",
            headers=tenant_headers,
            params={"openid": shared_social_openid},
        )
        assert tenant_social_users_response.status_code == 200
        assert {item["id"] for item in tenant_social_users_response.json()["items"]} == {
            str(tenant_social_user.id)
        }
        assert (
            client.get(
                f"{settings.API_V1_STR}/social/users/{default_social_user.id}",
                headers=tenant_headers,
            ).status_code
            == 404
        )
    finally:
        db.rollback()
        db.expire_all()
        if social_user_ids:
            db.exec(delete(SocialUser).where(SocialUser.id.in_(social_user_ids)))
        if social_client_ids:
            db.exec(delete(SocialClient).where(SocialClient.id.in_(social_client_ids)))
        if oauth_client_ids:
            db.exec(
                delete(OAuth2AccessToken).where(
                    OAuth2AccessToken.client_id.in_(
                        [default_oauth_client_code, tenant_oauth_client_code]
                    )
                )
            )
            db.exec(
                delete(OAuth2AuthorizationCode).where(
                    OAuth2AuthorizationCode.client_id.in_(
                        [default_oauth_client_code, tenant_oauth_client_code]
                    )
                )
            )
            db.exec(delete(OAuth2Client).where(OAuth2Client.id.in_(oauth_client_ids)))
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
