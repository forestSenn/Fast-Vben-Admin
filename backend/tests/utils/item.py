from sqlmodel import Session

from app import crud
from app.core.tenancy import get_active_tenant_membership
from app.models import Item, ItemCreate
from tests.utils.user import create_random_user
from tests.utils.utils import random_lower_string


def create_random_item(db: Session) -> Item:
    user = create_random_user(db)
    owner_id = user.id
    assert owner_id is not None
    title = random_lower_string()
    description = random_lower_string()
    item_in = ItemCreate(title=title, description=description)
    membership = get_active_tenant_membership(session=db, user_id=owner_id)
    assert membership is not None
    _, tenant = membership
    return crud.create_item(
        session=db,
        item_in=item_in,
        owner_id=owner_id,
        tenant_id=tenant.id,
    )
