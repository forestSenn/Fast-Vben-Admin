import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


class ItemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


class ItemPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None = None
    owner_id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ItemsPublic(BaseModel):
    items: list[ItemPublic]
    total: int
    page: int
    page_size: int
