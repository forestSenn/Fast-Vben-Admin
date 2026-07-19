import uuid
from unittest.mock import patch

import pyotp
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from app import crud
from app.core.config import settings
from app.core.mfa import encrypt_totp_secret, serialize_recovery_codes
from app.core.security import verify_password
from app.models import Post, User, UserCreate, UserPost
from tests.utils.user import create_random_user, user_authentication_headers
from tests.utils.utils import random_email, random_lower_string


def test_get_users_superuser_me(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.get(f"{settings.API_V1_STR}/users/me", headers=superuser_token_headers)
    current_user = r.json()
    assert current_user
    assert current_user["is_active"] is True
    assert current_user["is_superuser"]
    assert current_user["email"] == settings.FIRST_SUPERUSER


def test_get_users_normal_user_me(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    r = client.get(f"{settings.API_V1_STR}/users/me", headers=normal_user_token_headers)
    current_user = r.json()
    assert current_user
    assert current_user["is_active"] is True
    assert current_user["is_superuser"] is False
    assert current_user["email"] == settings.EMAIL_TEST_USER


def test_current_user_mfa_lifecycle(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    status_response = client.get(
        f"{settings.API_V1_STR}/users/me/mfa",
        headers=superuser_token_headers,
    )
    assert status_response.status_code == 200
    assert status_response.json()["enabled"] is False

    enable_without_setup = client.post(
        f"{settings.API_V1_STR}/users/me/mfa/enable",
        headers=superuser_token_headers,
        json={"code": "123456"},
    )
    assert enable_without_setup.status_code == 400
    assert enable_without_setup.json()["message"] == "MFA is not configured."

    setup_response = client.post(
        f"{settings.API_V1_STR}/users/me/mfa/setup",
        headers=superuser_token_headers,
    )
    assert setup_response.status_code == 200
    setup = setup_response.json()
    assert setup["secret"]
    assert setup["otpauth_uri"].startswith("otpauth://totp/")

    pending_status = client.get(
        f"{settings.API_V1_STR}/users/me/mfa",
        headers=superuser_token_headers,
    )
    assert pending_status.status_code == 200
    assert pending_status.json()["pending_setup"] is True

    enable_response = client.post(
        f"{settings.API_V1_STR}/users/me/mfa/enable",
        headers=superuser_token_headers,
        json={"code": pyotp.TOTP(setup["secret"]).now()},
    )
    assert enable_response.status_code == 200
    assert enable_response.json()["message"] == "MFA enabled successfully"
    assert len(enable_response.json()["recovery_codes"]) == 10

    enabled_status = client.get(
        f"{settings.API_V1_STR}/users/me/mfa",
        headers=superuser_token_headers,
    )
    assert enabled_status.status_code == 200
    assert enabled_status.json()["enabled"] is True
    assert enabled_status.json()["method"] == "totp"
    assert enabled_status.json()["recovery_codes_remaining"] == 10

    repeated_setup = client.post(
        f"{settings.API_V1_STR}/users/me/mfa/setup",
        headers=superuser_token_headers,
    )
    assert repeated_setup.status_code == 400
    assert repeated_setup.json()["message"] == "MFA has already been enabled."

    wrong_password = client.post(
        f"{settings.API_V1_STR}/users/me/mfa/disable",
        headers=superuser_token_headers,
        json={"current_password": "incorrect", "code": "123456"},
    )
    assert wrong_password.status_code == 400
    assert wrong_password.json()["message"] == "Incorrect password"

    wrong_code = client.post(
        f"{settings.API_V1_STR}/users/me/mfa/disable",
        headers=superuser_token_headers,
        json={
            "current_password": settings.FIRST_SUPERUSER_PASSWORD,
            "code": "123456",
        },
    )
    assert wrong_code.status_code == 400
    assert wrong_code.json()["message"] == "MFA verification code is invalid."

    disable_response = client.post(
        f"{settings.API_V1_STR}/users/me/mfa/disable",
        headers=superuser_token_headers,
        json={
            "current_password": settings.FIRST_SUPERUSER_PASSWORD,
            "code": pyotp.TOTP(setup["secret"]).now(),
        },
    )
    assert disable_response.status_code == 200
    assert disable_response.json()["message"] == "MFA disabled successfully"

    disabled_status = client.get(
        f"{settings.API_V1_STR}/users/me/mfa",
        headers=superuser_token_headers,
    )
    assert disabled_status.status_code == 200
    assert disabled_status.json()["enabled"] is False
    assert disabled_status.json()["pending_setup"] is False
    assert disabled_status.json()["recovery_codes_remaining"] == 0


def test_superuser_can_reset_user_mfa(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    user = crud.create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password=random_lower_string()),
    )
    user.mfa_enabled = True
    user.mfa_secret_encrypted = encrypt_totp_secret("JBSWY3DPEHPK3PXP")
    user.mfa_recovery_code_hashes = serialize_recovery_codes(["RECOVERY-CODE"])
    db.add(user)
    db.commit()

    response = client.post(
        f"{settings.API_V1_STR}/users/{user.id}/mfa/reset",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["message"] == "MFA reset successfully"

    audit_response = client.get(
        f"{settings.API_V1_STR}/logs/operation",
        headers=superuser_token_headers,
        params={"keyword": f"/api/v1/users/{user.id}/mfa/reset", "page_size": 20},
    )
    assert audit_response.status_code == 200
    assert any(
        log["method"] == "POST"
        and log["path"] == f"{settings.API_V1_STR}/users/{user.id}/mfa/reset"
        and log["status_code"] == 200
        for log in audit_response.json()["items"]
    )

    db.refresh(user)
    assert user.mfa_enabled is False
    assert user.mfa_secret_encrypted is None
    assert user.mfa_recovery_code_hashes is None


def test_create_user_new_email(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    with (
        patch("app.utils.send_email", return_value=None),
        patch("app.core.config.settings.SMTP_HOST", "smtp.example.com"),
        patch("app.core.config.settings.SMTP_USER", "admin@example.com"),
    ):
        username = random_email()
        password = random_lower_string()
        data = {"email": username, "password": password}
        r = client.post(
            f"{settings.API_V1_STR}/users",
            headers=superuser_token_headers,
            json=data,
        )
        assert 200 <= r.status_code < 300
        created_user = r.json()
        user = crud.get_user_by_email(session=db, email=username)
        assert user
        assert user.email == created_user["email"]


def test_get_existing_user_as_superuser(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    username = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=username, password=password)
    user = crud.create_user(session=db, user_create=user_in)
    user_id = user.id
    r = client.get(
        f"{settings.API_V1_STR}/users/{user_id}",
        headers=superuser_token_headers,
    )
    assert 200 <= r.status_code < 300
    api_user = r.json()
    existing_user = crud.get_user_by_email(session=db, email=username)
    assert existing_user
    assert existing_user.email == api_user["email"]


def test_get_non_existing_user_as_superuser(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.get(
        f"{settings.API_V1_STR}/users/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 404
    assert r.json()["message"] == "User not found"


def test_get_existing_user_current_user(client: TestClient, db: Session) -> None:
    username = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=username, password=password)
    user = crud.create_user(session=db, user_create=user_in)
    user_id = user.id

    login_data = {
        "username": username,
        "password": password,
    }
    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
    tokens = r.json()
    a_token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {a_token}"}

    r = client.get(
        f"{settings.API_V1_STR}/users/{user_id}",
        headers=headers,
    )
    assert 200 <= r.status_code < 300
    api_user = r.json()
    existing_user = crud.get_user_by_email(session=db, email=username)
    assert existing_user
    assert existing_user.email == api_user["email"]


def test_get_existing_user_permissions_error(
    db: Session,
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    user = create_random_user(db)

    r = client.get(
        f"{settings.API_V1_STR}/users/{user.id}",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 403
    assert r.json()["message"] == "The user doesn't have enough privileges"


def test_get_non_existing_user_permissions_error(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    user_id = uuid.uuid4()

    r = client.get(
        f"{settings.API_V1_STR}/users/{user_id}",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 403
    assert r.json()["message"] == "The user doesn't have enough privileges"


def test_create_user_existing_username(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    username = random_email()
    # username = email
    password = random_lower_string()
    user_in = UserCreate(email=username, password=password)
    crud.create_user(session=db, user_create=user_in)
    data = {"email": username, "password": password}
    r = client.post(
        f"{settings.API_V1_STR}/users",
        headers=superuser_token_headers,
        json=data,
    )
    created_user = r.json()
    assert r.status_code == 400
    assert "_id" not in created_user


def test_create_user_by_normal_user(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    username = random_email()
    password = random_lower_string()
    data = {"email": username, "password": password}
    r = client.post(
        f"{settings.API_V1_STR}/users",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 403


def test_retrieve_users(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    username = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=username, password=password)
    crud.create_user(session=db, user_create=user_in)

    username2 = random_email()
    password2 = random_lower_string()
    user_in2 = UserCreate(email=username2, password=password2)
    crud.create_user(session=db, user_create=user_in2)

    r = client.get(f"{settings.API_V1_STR}/users", headers=superuser_token_headers)
    all_users = r.json()

    assert len(all_users["items"]) > 1
    assert "total" in all_users
    assert all_users["page"] == 1
    assert all_users["page_size"] == 20
    for item in all_users["items"]:
        assert "email" in item


def test_retrieve_users_filters_by_active_status(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    active_user = crud.create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password=random_lower_string()),
    )
    inactive_user = crud.create_user(
        session=db,
        user_create=UserCreate(
            email=random_email(),
            is_active=False,
            password=random_lower_string(),
        ),
    )

    active_response = client.get(
        f"{settings.API_V1_STR}/users",
        headers=superuser_token_headers,
        params={"is_active": True, "page_size": 100},
    )
    inactive_response = client.get(
        f"{settings.API_V1_STR}/users",
        headers=superuser_token_headers,
        params={"is_active": False, "page_size": 100},
    )

    assert active_response.status_code == 200
    assert inactive_response.status_code == 200
    active_ids = {item["id"] for item in active_response.json()["items"]}
    inactive_ids = {item["id"] for item in inactive_response.json()["items"]}
    assert str(active_user.id) in active_ids
    assert str(inactive_user.id) not in active_ids
    assert str(inactive_user.id) in inactive_ids


def test_export_users(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/users/export",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "email" in response.text


def test_download_user_import_template(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/users/import-template",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "department_code" in response.text
    assert "role_codes" in response.text
    assert "post_codes" in response.text


def test_superuser_can_import_users_with_roles_and_posts(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    email = random_email()
    csv_content = (
        "email,password,full_name,department_code,role_codes,post_codes,"
        "is_active,is_superuser\n"
        f"{email},changethis,Imported User,headquarters,user,developer,true,false\n"
    )
    response = client.post(
        f"{settings.API_V1_STR}/users/import",
        headers=superuser_token_headers,
        files={"file": ("users.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 200
    assert response.json()["success"] == 1
    assert response.json()["failed"] == 0

    user = crud.get_user_by_email(session=db, email=email)
    assert user
    role_response = client.get(
        f"{settings.API_V1_STR}/users/{user.id}/roles",
        headers=superuser_token_headers,
    )
    post_response = client.get(
        f"{settings.API_V1_STR}/users/{user.id}/posts",
        headers=superuser_token_headers,
    )
    assert role_response.status_code == 200
    assert post_response.status_code == 200
    assert [role["code"] for role in role_response.json()] == ["user"]
    assert [post["code"] for post in post_response.json()] == ["developer"]

    db.delete(user)
    db.commit()


def test_user_import_returns_row_errors_without_blocking_valid_rows(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    email = random_email()
    csv_content = (
        "email,password,department_code,role_codes,post_codes\n"
        f"{email},changethis,headquarters,user,developer\n"
        f"{settings.FIRST_SUPERUSER},changethis,headquarters,user,developer\n"
    )
    response = client.post(
        f"{settings.API_V1_STR}/users/import",
        headers=superuser_token_headers,
        files={"file": ("users.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["success"] == 1
    assert result["failed"] == 1
    assert result["errors"][0]["row"] == 3
    assert "email already exists" in result["errors"][0]["error"]

    user = crud.get_user_by_email(session=db, email=email)
    assert user
    db.delete(user)
    db.commit()


def test_normal_user_cannot_import_users(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/users/import",
        headers=normal_user_token_headers,
        files={"file": ("users.csv", "email,password\nuser@example.com,changethis\n")},
    )

    assert response.status_code == 403


def test_update_user_me(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    full_name = "Updated Name"
    email = random_email()
    data = {"full_name": full_name, "email": email}
    r = client.patch(
        f"{settings.API_V1_STR}/users/me",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 200
    updated_user = r.json()
    assert updated_user["email"] == email
    assert updated_user["full_name"] == full_name

    user_query = select(User).where(User.email == email)
    user_db = db.exec(user_query).first()
    assert user_db
    assert user_db.email == email
    assert user_db.full_name == full_name


def test_update_password_me_revokes_existing_session(
    client: TestClient, db: Session
) -> None:
    password = random_lower_string()
    new_password = random_lower_string()
    user = crud.create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password=password),
    )
    headers = user_authentication_headers(
        client=client,
        email=user.email,
        password=password,
    )
    data = {
        "current_password": password,
        "new_password": new_password,
    }
    r = client.patch(
        f"{settings.API_V1_STR}/users/me/password",
        headers=headers,
        json=data,
    )
    assert r.status_code == 200
    updated_user = r.json()
    assert updated_user["message"] == "Password updated successfully"

    db.refresh(user)
    verified, _ = verify_password(new_password, user.hashed_password)
    assert verified

    rejected_response = client.get(
        f"{settings.API_V1_STR}/users/me",
        headers=headers,
    )
    assert rejected_response.status_code == 403


def test_update_password_me_incorrect_password(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    new_password = random_lower_string()
    data = {"current_password": new_password, "new_password": new_password}
    r = client.patch(
        f"{settings.API_V1_STR}/users/me/password",
        headers=superuser_token_headers,
        json=data,
    )
    assert r.status_code == 400
    updated_user = r.json()
    assert updated_user["message"] == "Incorrect password"


def test_update_user_me_email_exists(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    username = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=username, password=password)
    user = crud.create_user(session=db, user_create=user_in)

    data = {"email": user.email}
    r = client.patch(
        f"{settings.API_V1_STR}/users/me",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 409
    assert r.json()["message"] == "User with this email already exists"


def test_update_password_me_same_password_error(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {
        "current_password": settings.FIRST_SUPERUSER_PASSWORD,
        "new_password": settings.FIRST_SUPERUSER_PASSWORD,
    }
    r = client.patch(
        f"{settings.API_V1_STR}/users/me/password",
        headers=superuser_token_headers,
        json=data,
    )
    assert r.status_code == 400
    updated_user = r.json()
    assert (
        updated_user["message"] == "New password cannot be the same as the current one"
    )


def test_register_user_not_exposed(client: TestClient) -> None:
    username = random_email()
    password = random_lower_string()
    full_name = random_lower_string()
    data = {"email": username, "password": password, "full_name": full_name}
    r = client.post(
        f"{settings.API_V1_STR}/users/signup",
        json=data,
    )
    assert r.status_code in {404, 405}


def test_register_user_already_exists_not_exposed(client: TestClient) -> None:
    password = random_lower_string()
    full_name = random_lower_string()
    data = {
        "email": settings.FIRST_SUPERUSER,
        "password": password,
        "full_name": full_name,
    }
    r = client.post(
        f"{settings.API_V1_STR}/users/signup",
        json=data,
    )
    assert r.status_code in {404, 405}


def test_update_user(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    username = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=username, password=password)
    user = crud.create_user(session=db, user_create=user_in)

    data = {"full_name": "Updated_full_name"}
    r = client.patch(
        f"{settings.API_V1_STR}/users/{user.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert r.status_code == 200
    updated_user = r.json()

    assert updated_user["full_name"] == "Updated_full_name"

    user_query = select(User).where(User.email == username)
    user_db = db.exec(user_query).first()
    db.refresh(user_db)
    assert user_db
    assert user_db.full_name == "Updated_full_name"


def test_built_in_administrator_cannot_be_modified(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    protected_user = crud.get_user_by_email(
        session=db,
        email=settings.FIRST_SUPERUSER,
    )
    assert protected_user is not None

    responses = [
        client.patch(
            f"{settings.API_V1_STR}/users/{protected_user.id}",
            headers=superuser_token_headers,
            json={"full_name": "Changed administrator"},
        ),
        client.put(
            f"{settings.API_V1_STR}/users/{protected_user.id}/roles",
            headers=superuser_token_headers,
            json={"role_ids": []},
        ),
        client.put(
            f"{settings.API_V1_STR}/users/{protected_user.id}/posts",
            headers=superuser_token_headers,
            json={"post_ids": []},
        ),
        client.post(
            f"{settings.API_V1_STR}/users/{protected_user.id}/mfa/reset",
            headers=superuser_token_headers,
        ),
        client.delete(
            f"{settings.API_V1_STR}/users/{protected_user.id}",
            headers=superuser_token_headers,
        ),
    ]

    assert all(response.status_code == 403 for response in responses)
    assert all(response.json()["code"] == "USER_PROTECTED" for response in responses)


def test_update_user_not_exists(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {"full_name": "Updated_full_name"}
    r = client.patch(
        f"{settings.API_V1_STR}/users/{uuid.uuid4()}",
        headers=superuser_token_headers,
        json=data,
    )
    assert r.status_code == 404
    assert r.json()["message"] == "The user with this id does not exist in the system"


def test_update_user_email_exists(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    username = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=username, password=password)
    user = crud.create_user(session=db, user_create=user_in)

    username2 = random_email()
    password2 = random_lower_string()
    user_in2 = UserCreate(email=username2, password=password2)
    user2 = crud.create_user(session=db, user_create=user_in2)

    data = {"email": user2.email}
    r = client.patch(
        f"{settings.API_V1_STR}/users/{user.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert r.status_code == 409
    assert r.json()["message"] == "User with this email already exists"


def test_delete_user_me_not_exposed(client: TestClient, db: Session) -> None:
    username = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=username, password=password)
    user = crud.create_user(session=db, user_create=user_in)
    user_id = user.id

    login_data = {
        "username": username,
        "password": password,
    }
    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
    tokens = r.json()
    a_token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {a_token}"}

    r = client.delete(
        f"{settings.API_V1_STR}/users/me",
        headers=headers,
    )
    assert r.status_code in {403, 404, 405, 422}
    result = db.exec(select(User).where(User.id == user_id)).first()
    assert result is not None

    user_query = select(User).where(User.id == user_id)
    user_db = db.execute(user_query).first()
    assert user_db is not None


def test_delete_user_me_as_superuser(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.delete(
        f"{settings.API_V1_STR}/users/me",
        headers=superuser_token_headers,
    )
    assert r.status_code == 422


def test_delete_user_super_user(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    username = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=username, password=password)
    user = crud.create_user(session=db, user_create=user_in)
    user_id = user.id
    r = client.delete(
        f"{settings.API_V1_STR}/users/{user_id}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 204
    assert not r.content
    db.expire_all()
    result = db.exec(select(User).where(User.id == user_id)).first()
    assert result is not None
    assert not result.is_active
    assert result.archived_at is not None


def test_delete_user_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.delete(
        f"{settings.API_V1_STR}/users/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 404
    assert r.json()["message"] == "User not found"


def test_delete_user_current_super_user_error(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    super_user = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    assert super_user
    user_id = super_user.id

    r = client.delete(
        f"{settings.API_V1_STR}/users/{user_id}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 403
    assert r.json()["message"] == "Built-in administrator cannot be modified"


def test_delete_user_without_privileges(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    username = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=username, password=password)
    user = crud.create_user(session=db, user_create=user_in)

    r = client.delete(
        f"{settings.API_V1_STR}/users/{user.id}",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 403
    assert r.json()["message"] == "The user doesn't have enough privileges"


def test_superuser_can_update_and_read_user_posts(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    user = crud.create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password=random_lower_string()),
    )
    post = Post(code=f"post_{random_lower_string()}", name="User post")
    db.add(post)
    db.commit()
    db.refresh(post)

    try:
        update_response = client.put(
            f"{settings.API_V1_STR}/users/{user.id}/posts",
            headers=superuser_token_headers,
            json={"post_ids": [str(post.id)]},
        )
        assert update_response.status_code == 200
        assert update_response.json() == [str(post.id)]

        read_response = client.get(
            f"{settings.API_V1_STR}/users/{user.id}/posts",
            headers=superuser_token_headers,
        )
        assert read_response.status_code == 200
        posts = read_response.json()
        assert len(posts) == 1
        assert posts[0]["id"] == str(post.id)
    finally:
        db.exec(delete(UserPost).where(UserPost.user_id == user.id))
        db.delete(user)
        db.delete(post)
        db.commit()


def test_update_user_posts_rejects_unknown_post(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    user = crud.create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password=random_lower_string()),
    )

    try:
        response = client.put(
            f"{settings.API_V1_STR}/users/{user.id}/posts",
            headers=superuser_token_headers,
            json={"post_ids": [str(uuid.uuid4())]},
        )
        assert response.status_code == 400
        assert response.json()["message"] == "Some posts do not exist"
    finally:
        db.delete(user)
        db.commit()
