from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import (
    ModuleRegistry,
    ModuleStateAudit,
    OutboxEvent,
    OutboxEventStatus,
    Tenant,
    get_datetime_utc,
)


def test_module_state_and_entitlement_control_items_access(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    registry_response = client.get(
        f"{settings.API_V1_STR}/platform/modules",
        headers=superuser_token_headers,
    )
    assert registry_response.status_code == 200
    assert any(module["code"] == "items" for module in registry_response.json())

    tenant = db.exec(select(Tenant).where(Tenant.code == "default")).one()
    module = db.get(ModuleRegistry, "items")
    assert module is not None

    try:
        disabled_response = client.patch(
            f"{settings.API_V1_STR}/platform/modules/items",
            headers=superuser_token_headers,
            json={"desired_state": "disabled", "reason": "test global disable"},
        )
        assert disabled_response.status_code == 200
        response = client.get(
            f"{settings.API_V1_STR}/items", headers=superuser_token_headers
        )
        assert response.status_code == 503
        assert response.json()["code"] == "MODULE_UNAVAILABLE"
        menus = client.get(
            f"{settings.API_V1_STR}/menus/me", headers=superuser_token_headers
        )
        assert menus.status_code == 200
        assert all(
            not (menu.get("permission_code") or "").startswith("business:item:")
            for menu in menus.json()
        )
        permissions = client.get(
            f"{settings.API_V1_STR}/permissions/me", headers=superuser_token_headers
        )
        assert permissions.status_code == 200
        assert all(not permission.startswith("business:item:") for permission in permissions.json())

        assert (
            client.patch(
                f"{settings.API_V1_STR}/platform/modules/items",
                headers=superuser_token_headers,
                json={"desired_state": "enabled", "reason": "test restore"},
            ).status_code
            == 200
        )

        plan_response = client.put(
            f"{settings.API_V1_STR}/platform/modules/plans/{tenant.plan_id}/items",
            headers=superuser_token_headers,
            json={"is_enabled": False},
        )
        assert plan_response.status_code == 200
        response = client.get(
            f"{settings.API_V1_STR}/items", headers=superuser_token_headers
        )
        assert response.status_code == 403
        assert response.json()["code"] == "TENANT_MODULE_ENTITLEMENT_REQUIRED"

        assert (
            client.put(
                f"{settings.API_V1_STR}/platform/modules/plans/{tenant.plan_id}/items",
                headers=superuser_token_headers,
                json={"is_enabled": True},
            ).status_code
            == 200
        )

        preference_response = client.put(
            f"{settings.API_V1_STR}/platform/modules/tenants/{tenant.id}/items",
            headers=superuser_token_headers,
            json={"is_enabled": False},
        )
        assert preference_response.status_code == 200
        response = client.get(
            f"{settings.API_V1_STR}/items", headers=superuser_token_headers
        )
        assert response.status_code == 403
        assert response.json()["code"] == "TENANT_MODULE_DISABLED"
    finally:
        client.patch(
            f"{settings.API_V1_STR}/platform/modules/items",
            headers=superuser_token_headers,
            json={"desired_state": "enabled", "reason": "test cleanup"},
        )
        client.put(
            f"{settings.API_V1_STR}/platform/modules/plans/{tenant.plan_id}/items",
            headers=superuser_token_headers,
            json={"is_enabled": True},
        )
        client.put(
            f"{settings.API_V1_STR}/platform/modules/tenants/{tenant.id}/items",
            headers=superuser_token_headers,
            json={"is_enabled": True},
        )

    audits = db.exec(
        select(ModuleStateAudit).where(ModuleStateAudit.module_code == "items")
    ).all()
    assert any(audit.action == "module.desired_state.changed" for audit in audits)
    assert any(audit.action == "plan.module_entitlement.changed" for audit in audits)
    assert any(audit.action == "tenant.module_preference.changed" for audit in audits)


def test_dead_letter_events_can_be_listed_and_requeued(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    event = OutboxEvent(
        module_code="platform",
        event_type="test.dead-letter.v1",
        event_version=1,
        aggregate_id="test-event",
        payload="{}",
        occurred_at=get_datetime_utc(),
        available_at=get_datetime_utc(),
        status=OutboxEventStatus.DEAD_LETTER,
        dead_lettered_at=get_datetime_utc(),
    )
    db.add(event)
    db.commit()
    try:
        listed = client.get(
            f"{settings.API_V1_STR}/platform/modules/events/dead-letter",
            headers=superuser_token_headers,
        )
        assert listed.status_code == 200
        assert str(event.id) in {entry["id"] for entry in listed.json()}

        retried = client.post(
            f"{settings.API_V1_STR}/platform/modules/events/{event.id}/retry",
            headers=superuser_token_headers,
        )
        assert retried.status_code == 200
        db.refresh(event)
        assert event.status == OutboxEventStatus.PENDING
        assert event.attempts == 0
    finally:
        db.delete(event)
        db.commit()
