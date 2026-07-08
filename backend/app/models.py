import uuid
from datetime import UTC, datetime

from pydantic import EmailStr
from sqlalchemy import DateTime
from sqlmodel import Field, Relationship, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)
    department_id: uuid.UUID | None = Field(default=None, foreign_key="department.id")
    avatar_url: str | None = Field(default=None, max_length=500)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(SQLModel):
    email: EmailStr | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    is_superuser: bool | None = None
    full_name: str | None = Field(default=None, max_length=255)
    department_id: uuid.UUID | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    items: list[Item] = Relationship(back_populates="owner", cascade_delete=True)


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UsersPublic(SQLModel):
    items: list[UserPublic]
    total: int
    page: int
    page_size: int


class DepartmentBase(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=100, unique=True, index=True)
    parent_id: uuid.UUID | None = Field(default=None, foreign_key="department.id")
    leader_user_id: uuid.UUID | None = Field(default=None, foreign_key="user.id")
    sort: int = 0
    is_active: bool = True


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, min_length=1, max_length=100)
    parent_id: uuid.UUID | None = None
    leader_user_id: uuid.UUID | None = None
    sort: int | None = None
    is_active: bool | None = None


class Department(DepartmentBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class DepartmentPublic(DepartmentBase):
    id: uuid.UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DepartmentsPublic(SQLModel):
    items: list[DepartmentPublic]
    total: int
    page: int
    page_size: int


class UserRole(SQLModel, table=True):
    user_id: uuid.UUID = Field(
        foreign_key="user.id", primary_key=True, ondelete="CASCADE"
    )
    role_id: uuid.UUID = Field(
        foreign_key="role.id", primary_key=True, ondelete="CASCADE"
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class RoleMenu(SQLModel, table=True):
    role_id: uuid.UUID = Field(
        foreign_key="role.id", primary_key=True, ondelete="CASCADE"
    )
    menu_id: uuid.UUID = Field(
        foreign_key="menu.id", primary_key=True, ondelete="CASCADE"
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class RoleBase(SQLModel):
    code: str = Field(min_length=1, max_length=100, unique=True, index=True)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    sort: int = 0
    is_active: bool = True
    is_system: bool = False


class RoleCreate(RoleBase):
    pass


class RoleUpdate(SQLModel):
    code: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    sort: int | None = None
    is_active: bool | None = None
    is_system: bool | None = None


class Role(RoleBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class RolePublic(RoleBase):
    id: uuid.UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RolesPublic(SQLModel):
    items: list[RolePublic]
    total: int
    page: int
    page_size: int


class RoleMenuUpdate(SQLModel):
    menu_ids: list[uuid.UUID]


class UserRoleUpdate(SQLModel):
    role_ids: list[uuid.UUID]


class MenuBase(SQLModel):
    title: str = Field(min_length=1, max_length=100)
    type: str = Field(default="menu", max_length=20)
    parent_id: uuid.UUID | None = Field(default=None, foreign_key="menu.id")
    route_path: str | None = Field(default=None, max_length=255)
    route_name: str | None = Field(default=None, max_length=100)
    component: str | None = Field(default=None, max_length=255)
    icon: str | None = Field(default=None, max_length=100)
    permission_code: str | None = Field(default=None, max_length=100, index=True)
    sort: int = 0
    is_visible: bool = True
    is_keep_alive: bool = False
    is_active: bool = True


class MenuCreate(MenuBase):
    pass


class MenuUpdate(SQLModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    type: str | None = Field(default=None, max_length=20)
    parent_id: uuid.UUID | None = None
    route_path: str | None = Field(default=None, max_length=255)
    route_name: str | None = Field(default=None, max_length=100)
    component: str | None = Field(default=None, max_length=255)
    icon: str | None = Field(default=None, max_length=100)
    permission_code: str | None = Field(default=None, max_length=100)
    sort: int | None = None
    is_visible: bool | None = None
    is_keep_alive: bool | None = None
    is_active: bool | None = None


class Menu(MenuBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class MenuPublic(MenuBase):
    id: uuid.UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MenusPublic(SQLModel):
    items: list[MenuPublic]
    total: int
    page: int
    page_size: int


class DictionaryTypeBase(SQLModel):
    code: str = Field(min_length=1, max_length=100, unique=True, index=True)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    is_active: bool = True


class DictionaryTypeCreate(DictionaryTypeBase):
    pass


class DictionaryTypeUpdate(SQLModel):
    code: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class DictionaryType(DictionaryTypeBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class DictionaryTypePublic(DictionaryTypeBase):
    id: uuid.UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DictionaryTypesPublic(SQLModel):
    items: list[DictionaryTypePublic]
    total: int
    page: int
    page_size: int


class DictionaryItemBase(SQLModel):
    type_id: uuid.UUID = Field(foreign_key="dictionarytype.id")
    label: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=100)
    color: str | None = Field(default=None, max_length=50)
    sort: int = 0
    is_active: bool = True
    extra_data: str | None = Field(default=None, max_length=1000)


class DictionaryItemCreate(DictionaryItemBase):
    pass


class DictionaryItemUpdate(SQLModel):
    type_id: uuid.UUID | None = None
    label: str | None = Field(default=None, min_length=1, max_length=100)
    value: str | None = Field(default=None, min_length=1, max_length=100)
    color: str | None = Field(default=None, max_length=50)
    sort: int | None = None
    is_active: bool | None = None
    extra_data: str | None = Field(default=None, max_length=1000)


class DictionaryItem(DictionaryItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class DictionaryItemPublic(DictionaryItemBase):
    id: uuid.UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DictionaryItemsPublic(SQLModel):
    items: list[DictionaryItemPublic]
    total: int
    page: int
    page_size: int


class SystemSettingBase(SQLModel):
    key: str = Field(min_length=1, max_length=100, unique=True, index=True)
    name: str = Field(min_length=1, max_length=100)
    value: str = Field(default="", max_length=2000)
    value_type: str = Field(default="string", max_length=20)
    group: str = Field(default="default", max_length=100)
    description: str | None = Field(default=None, max_length=255)
    is_public: bool = False
    is_system: bool = False


class SystemSettingCreate(SystemSettingBase):
    pass


class SystemSettingUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    value: str | None = Field(default=None, max_length=2000)
    value_type: str | None = Field(default=None, max_length=20)
    group: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    is_public: bool | None = None
    is_system: bool | None = None


class SystemSetting(SystemSettingBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class SystemSettingPublic(SystemSettingBase):
    id: uuid.UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SystemSettingsPublic(SQLModel):
    items: list[SystemSettingPublic]
    total: int
    page: int
    page_size: int


class LoginLogBase(SQLModel):
    user_id: uuid.UUID | None = None
    email: str | None = Field(default=None, max_length=255)
    ip: str | None = Field(default=None, max_length=100)
    user_agent: str | None = Field(default=None, max_length=500)
    status: str = Field(max_length=20)
    failure_reason: str | None = Field(default=None, max_length=255)


class LoginLog(LoginLogBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class LoginLogPublic(LoginLogBase):
    id: uuid.UUID
    created_at: datetime | None = None


class LoginLogsPublic(SQLModel):
    items: list[LoginLogPublic]
    total: int
    page: int
    page_size: int


class OperationLogBase(SQLModel):
    user_id: uuid.UUID | None = None
    email: str | None = Field(default=None, max_length=255)
    module: str = Field(max_length=100)
    action: str = Field(max_length=100)
    method: str = Field(max_length=20)
    path: str = Field(max_length=500)
    status_code: int
    duration_ms: int
    ip: str | None = Field(default=None, max_length=100)
    user_agent: str | None = Field(default=None, max_length=500)
    request_summary: str | None = Field(default=None, max_length=1000)
    response_summary: str | None = Field(default=None, max_length=1000)


class OperationLog(OperationLogBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class OperationLogPublic(OperationLogBase):
    id: uuid.UUID
    created_at: datetime | None = None


class OperationLogsPublic(SQLModel):
    items: list[OperationLogPublic]
    total: int
    page: int
    page_size: int


class FileAssetBase(SQLModel):
    original_name: str = Field(max_length=255)
    stored_name: str = Field(max_length=255)
    content_type: str | None = Field(default=None, max_length=100)
    extension: str | None = Field(default=None, max_length=20)
    size: int
    sha256: str = Field(max_length=64, index=True)
    storage_provider: str = Field(default="local", max_length=50)
    storage_path: str = Field(max_length=500)
    public_url: str | None = Field(default=None, max_length=500)
    uploader_id: uuid.UUID | None = None
    is_public: bool = False


class FileAsset(FileAssetBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class FileAssetPublic(FileAssetBase):
    id: uuid.UUID
    created_at: datetime | None = None


class FileAssetsPublic(SQLModel):
    items: list[FileAssetPublic]
    total: int
    page: int
    page_size: int


class NoticeBase(SQLModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=10000)
    type: str = Field(default="notice", max_length=50)
    priority: int = 0
    status: str = Field(default="draft", max_length=20)
    published_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore


class NoticeCreate(SQLModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=10000)
    type: str = Field(default="notice", max_length=50)
    priority: int = 0


class NoticeUpdate(SQLModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1, max_length=10000)
    type: str | None = Field(default=None, max_length=50)
    priority: int | None = None
    status: str | None = Field(default=None, max_length=20)


class Notice(NoticeBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_by: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class NoticePublic(NoticeBase):
    id: uuid.UUID
    created_by: uuid.UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class NoticesPublic(SQLModel):
    items: list[NoticePublic]
    total: int
    page: int
    page_size: int


class UserMessageBase(SQLModel):
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    notice_id: uuid.UUID | None = Field(
        default=None, foreign_key="notice.id", ondelete="SET NULL"
    )
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=10000)
    type: str = Field(default="notice", max_length=50)
    is_read: bool = False
    read_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore


class UserMessage(UserMessageBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class UserMessagePublic(UserMessageBase):
    id: uuid.UUID
    created_at: datetime | None = None


class UserMessagesPublic(SQLModel):
    items: list[UserMessagePublic]
    total: int
    page: int
    page_size: int


# Shared properties
class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(SQLModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ItemsPublic(SQLModel):
    items: list[ItemPublic]
    total: int
    page: int
    page_size: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)
