from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from app.core.config import settings
from app.core.db import engine, init_db
from app.main import app
from app.models import (
    DictionaryItem,
    DictionaryType,
    EventConsumerReceipt,
    OutboxEvent,
    User,
)
from app.modules.items.infrastructure.models import Item
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import get_superuser_token_headers


@pytest.fixture(scope="session", autouse=True)
def disable_slider_captcha() -> Generator[None]:
    original = settings.LOGIN_SLIDER_CAPTCHA_ENABLED
    settings.LOGIN_SLIDER_CAPTCHA_ENABLED = False
    yield
    settings.LOGIN_SLIDER_CAPTCHA_ENABLED = original


def cleanup_test_dictionaries(session: Session) -> None:
    test_types = session.exec(
        select(DictionaryType).where(DictionaryType.name == "测试字典")
    ).all()
    for type_ in test_types:
        items = session.exec(
            select(DictionaryItem).where(DictionaryItem.type_id == type_.id)
        ).all()
        for item in items:
            session.delete(item)
        session.delete(type_)
    session.commit()


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session]:
    with Session(engine) as session:
        init_db(session)
        cleanup_test_dictionaries(session)
        session.execute(delete(EventConsumerReceipt))
        session.execute(delete(OutboxEvent))
        session.commit()
        yield session
        cleanup_test_dictionaries(session)
        session.execute(delete(EventConsumerReceipt))
        session.execute(delete(OutboxEvent))
        statement = delete(Item)
        session.execute(statement)
        statement = delete(User).where(User.email != settings.FIRST_SUPERUSER)
        session.execute(statement)
        session.commit()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )
