from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import crud
from app.core.config import settings
from app.core.tenancy import get_active_tenant_membership
from app.models import OutboxEvent, User, UserCreate
from app.modules.items.infrastructure.models import Item
from tests.utils.utils import random_email, random_lower_string


def test_deleting_user_archives_identity_and_preserves_items(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    user = crud.create_user(
        session=db,
        user_create=UserCreate(
            email=random_email(), password=f"pA{random_lower_string()}123!"
        ),
    )
    membership = get_active_tenant_membership(session=db, user_id=user.id)
    assert membership is not None
    _, tenant = membership
    item = Item(
        title=random_lower_string(),
        owner_id=user.id,
        tenant_id=tenant.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    try:
        response = client.delete(
            f"{settings.API_V1_STR}/users/{user.id}",
            headers=superuser_token_headers,
        )
        assert response.status_code == 204
        db.expire_all()
        archived_user = db.get(User, user.id)
        assert archived_user is not None
        assert not archived_user.is_active
        assert archived_user.archived_at is not None
        assert db.get(Item, item.id) is not None
        event = db.exec(
            select(OutboxEvent).where(
                OutboxEvent.event_type == "platform.user.archived",
                OutboxEvent.aggregate_id == str(user.id),
            )
        ).first()
        assert event is not None
    finally:
        db.delete(item)
        db.delete(user)
        db.commit()
