import uuid
from collections.abc import Collection

from sqlmodel import Session, select

from app.models import User
from app.platform.public_api.users import UserSummary


class SqlUserDirectory:
    """Platform-owned adapter for the narrow user lookup contract."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_users(self, user_ids: Collection[uuid.UUID]) -> list[UserSummary]:
        if not user_ids:
            return []
        users = self._session.exec(select(User).where(User.id.in_(user_ids))).all()
        return [
            UserSummary(
                id=user.id,
                full_name=user.full_name,
                email=user.email,
                is_active=user.is_active,
            )
            for user in users
        ]

    def validate_active_users(self, user_ids: Collection[uuid.UUID]) -> None:
        requested = set(user_ids)
        users = self.get_users(requested)
        active_ids = {user.id for user in users if user.is_active}
        if requested != active_ids:
            raise ValueError("One or more users are missing or inactive")
