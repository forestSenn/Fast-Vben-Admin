import uuid
from collections.abc import Collection
from typing import Protocol

from pydantic import BaseModel, ConfigDict


class UserSummary(BaseModel):
    """A read-only user projection that does not expose the platform ORM model."""

    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    full_name: str | None = None
    email: str
    is_active: bool


class UserDirectory(Protocol):
    def get_users(self, user_ids: Collection[uuid.UUID]) -> list[UserSummary]: ...

    def validate_active_users(self, user_ids: Collection[uuid.UUID]) -> None: ...
