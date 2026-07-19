import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import EmailStr
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
DEFAULT_TENANT_PLAN_ID = uuid.UUID("00000000-0000-4000-8000-000000001001")
DEFAULT_TENANT_TEMPLATE_ID = uuid.UUID("00000000-0000-4000-8000-000000002001")


class DataScope(StrEnum):
    ALL = "all"
    DEPARTMENT = "department"
    DEPARTMENT_AND_CHILDREN = "department_and_children"
    SELF = "self"
    CUSTOM = "custom"


class TenantLifecycleStatus(StrEnum):
    TRIAL = "trial"
    FORMAL = "formal"
    FROZEN = "frozen"
    EXPIRED = "expired"
    ARCHIVED = "archived"


class TenantLifecycleAction(StrEnum):
    CONVERT_TO_FORMAL = "convert_to_formal"
    RENEW = "renew"
    FREEZE = "freeze"
    UNFREEZE = "unfreeze"
    ARCHIVE = "archive"


class ModuleDesiredState(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    UNINSTALL_PENDING = "uninstall_pending"


class ModuleObservedState(StrEnum):
    BUNDLED = "bundled"
    MIGRATING = "migrating"
    READY = "ready"
    DEGRADED = "degraded"


class ModuleEntitlementEffect(StrEnum):
    GRANT = "grant"
    REVOKE = "revoke"


class OutboxEventStatus(StrEnum):
    PENDING = "pending"
    PUBLISHED = "published"
    DEAD_LETTER = "dead_letter"


class CapabilityBindingStatus(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"


class TenantPlanBase(SQLModel):
    code: str = Field(min_length=1, max_length=100, unique=True, index=True)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    max_members: int | None = Field(default=None, ge=1)
    max_file_assets: int | None = Field(default=None, ge=1)
    max_storage_bytes: int | None = Field(default=None, ge=1, sa_type=BigInteger)  # type: ignore
    is_default: bool = False
    is_active: bool = True


class TenantPlan(TenantPlanBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class TenantPlanCreate(TenantPlanBase):
    type: int = 0
    logo: str | None = Field(default=None, max_length=500)
    price: float = Field(default=0, ge=0)
    published: int = 0
    order_num: int = Field(default=1, ge=0)
    remark: str | None = Field(default=None, max_length=500)


class TenantPlanUpdate(SQLModel):
    code: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    max_members: int | None = Field(default=None, ge=1)
    max_file_assets: int | None = Field(default=None, ge=1)
    max_storage_bytes: int | None = Field(default=None, ge=1)
    is_default: bool | None = None
    is_active: bool | None = None
    type: int | None = None
    logo: str | None = Field(default=None, max_length=500)
    price: float | None = Field(default=None, ge=0)
    published: int | None = None
    order_num: int | None = Field(default=None, ge=0)
    remark: str | None = Field(default=None, max_length=500)


class TenantPlanPublic(TenantPlanBase):
    id: uuid.UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None
    type: int = 0
    logo: str | None = None
    price: float = 0
    published: int = 0
    order_num: int = 1
    subscription_num: int = 0
    subscription_total_amount: float = 0
    remark: str | None = None
    menu_count: int = 0


class TenantPlansPublic(SQLModel):
    items: list[TenantPlanPublic]
    total: int
    page: int
    page_size: int


class TenantInitializationTemplateBase(SQLModel):
    code: str = Field(min_length=1, max_length=100, unique=True, index=True)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    root_department_code: str = Field(
        default="headquarters", min_length=1, max_length=100
    )
    root_department_name: str = Field(default="总部", min_length=1, max_length=100)
    seed_posts: bool = True
    seed_dictionaries: bool = True
    seed_settings: bool = True
    seed_storage_channels: bool = True
    seed_message_templates: bool = True
    seed_sms_channels: bool = True
    seed_mail_accounts: bool = True
    is_default: bool = False
    is_active: bool = True


class TenantInitializationTemplate(TenantInitializationTemplateBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class TenantInitializationTemplateCreate(TenantInitializationTemplateBase):
    pass


class TenantInitializationTemplateUpdate(SQLModel):
    code: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    root_department_code: str | None = Field(default=None, min_length=1, max_length=100)
    root_department_name: str | None = Field(default=None, min_length=1, max_length=100)
    seed_posts: bool | None = None
    seed_dictionaries: bool | None = None
    seed_settings: bool | None = None
    seed_storage_channels: bool | None = None
    seed_message_templates: bool | None = None
    seed_sms_channels: bool | None = None
    seed_mail_accounts: bool | None = None
    is_default: bool | None = None
    is_active: bool | None = None


class TenantInitializationTemplatePublic(TenantInitializationTemplateBase):
    id: uuid.UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TenantInitializationTemplatesPublic(SQLModel):
    items: list[TenantInitializationTemplatePublic]
    total: int
    page: int
    page_size: int


class TenantBase(SQLModel):
    code: str = Field(min_length=1, max_length=100, unique=True, index=True)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool = True


class Tenant(TenantBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    plan_id: uuid.UUID = Field(
        default=DEFAULT_TENANT_PLAN_ID,
        foreign_key="tenantplan.id",
        index=True,
        ondelete="RESTRICT",
    )
    initialization_template_id: uuid.UUID = Field(
        default=DEFAULT_TENANT_TEMPLATE_ID,
        foreign_key="tenantinitializationtemplate.id",
        index=True,
        ondelete="RESTRICT",
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class TenantPublic(TenantBase):
    id: uuid.UUID
    plan_id: uuid.UUID
    plan_name: str | None = None
    initialization_template_id: uuid.UUID
    initialization_template_name: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    contact_user_id: uuid.UUID | None = None
    contact_name: str | None = None
    contact_mobile: str | None = None
    industry: int | None = None
    type: int | None = None
    address_code: str | None = None
    address_detail: str | None = None
    qualifications: str | None = None
    website: str | None = None
    recharge_amount: float = 0
    payment_amount: float = 0
    balance_amount: float = 0
    account_count: int | None = None
    current_account_count: int = 0
    lifecycle_status: TenantLifecycleStatus = TenantLifecycleStatus.FORMAL
    effective_at: datetime | None = None
    trial_ends_at: datetime | None = None
    service_expires_at: datetime | None = None
    frozen_at: datetime | None = None
    frozen_reason: str | None = None
    owner_name: str | None = None
    customer_source: str | None = None
    follow_up_notes: str | None = None


class TenantCreate(TenantBase):
    plan_id: uuid.UUID | None = None
    initialization_template_id: uuid.UUID | None = None
    contact_name: str | None = Field(default=None, max_length=100)
    contact_mobile: str | None = Field(default=None, max_length=32)
    industry: int | None = None
    type: int | None = None
    address_code: str | None = Field(default=None, max_length=100)
    address_detail: str | None = Field(default=None, max_length=255)
    qualifications: str | None = Field(default=None, max_length=500)
    website: str | None = Field(default=None, max_length=255)
    account_count: int | None = Field(default=None, ge=0)
    username: EmailStr | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    lifecycle_status: TenantLifecycleStatus = TenantLifecycleStatus.FORMAL
    effective_at: datetime | None = None
    trial_ends_at: datetime | None = None
    service_expires_at: datetime | None = None
    owner_name: str | None = Field(default=None, max_length=100)
    customer_source: str | None = Field(default=None, max_length=100)
    follow_up_notes: str | None = Field(default=None, max_length=1000)


class TenantUpdate(SQLModel):
    code: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
    plan_id: uuid.UUID | None = None
    contact_name: str | None = Field(default=None, max_length=100)
    contact_mobile: str | None = Field(default=None, max_length=32)
    industry: int | None = None
    type: int | None = None
    address_code: str | None = Field(default=None, max_length=100)
    address_detail: str | None = Field(default=None, max_length=255)
    qualifications: str | None = Field(default=None, max_length=500)
    website: str | None = Field(default=None, max_length=255)
    account_count: int | None = Field(default=None, ge=0)
    lifecycle_status: TenantLifecycleStatus | None = None
    effective_at: datetime | None = None
    trial_ends_at: datetime | None = None
    service_expires_at: datetime | None = None
    frozen_reason: str | None = Field(default=None, max_length=500)
    owner_name: str | None = Field(default=None, max_length=100)
    customer_source: str | None = Field(default=None, max_length=100)
    follow_up_notes: str | None = Field(default=None, max_length=1000)


class TenantsPublic(SQLModel):
    items: list[TenantPublic]
    total: int
    page: int
    page_size: int


class TenantMembershipPublic(SQLModel):
    tenant: TenantPublic
    is_active: bool
    is_default: bool
    is_current: bool
    created_at: datetime | None = None


class TenantSwitchRequest(SQLModel):
    tenant_id: uuid.UUID


class TenantUsagePublic(SQLModel):
    tenant_id: uuid.UUID
    plan: TenantPlanPublic
    members: int
    file_assets: int
    storage_bytes: int


class TenantLifecycleActionRequest(SQLModel):
    action: TenantLifecycleAction
    service_expires_at: datetime | None = None
    frozen_reason: str | None = Field(default=None, max_length=500)


class TenantMenuSyncResult(SQLModel):
    success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0


class TenantProfile(SQLModel, table=True):
    tenant_id: uuid.UUID = Field(
        foreign_key="tenant.id", primary_key=True, ondelete="CASCADE"
    )
    contact_user_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="user.id",
        ondelete="SET NULL",
    )
    contact_name: str | None = Field(default=None, max_length=100)
    contact_mobile: str | None = Field(default=None, max_length=32)
    industry: int | None = None
    tenant_type: int | None = None
    address_code: str | None = Field(default=None, max_length=100)
    address_detail: str | None = Field(default=None, max_length=255)
    qualifications: str | None = Field(default=None, max_length=500)
    website: str | None = Field(default=None, max_length=255)
    recharge_amount: float = 0
    payment_amount: float = 0
    balance_amount: float = 0
    account_count: int | None = Field(default=None, ge=0)
    lifecycle_status: TenantLifecycleStatus = Field(
        default=TenantLifecycleStatus.FORMAL,
        sa_type=String(32),
        index=True,
    )
    lifecycle_status_before_freeze: TenantLifecycleStatus | None = Field(
        default=None,
        sa_type=String(32),
    )
    effective_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    trial_ends_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
        index=True,
    )
    service_expires_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
        index=True,
    )
    frozen_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    frozen_reason: str | None = Field(default=None, max_length=500)
    owner_name: str | None = Field(default=None, max_length=100, index=True)
    customer_source: str | None = Field(default=None, max_length=100, index=True)
    follow_up_notes: str | None = Field(default=None, max_length=1000)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class TenantPlanProfile(SQLModel, table=True):
    plan_id: uuid.UUID = Field(
        foreign_key="tenantplan.id", primary_key=True, ondelete="CASCADE"
    )
    package_type: int = 0
    logo: str | None = Field(default=None, max_length=500)
    price: float = Field(default=0, ge=0)
    published: int = 0
    order_num: int = Field(default=1, ge=0)
    subscription_num: int = Field(default=0, ge=0)
    subscription_total_amount: float = Field(default=0, ge=0)
    remark: str | None = Field(default=None, max_length=500)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class TenantPlanMenu(SQLModel, table=True):
    plan_id: uuid.UUID = Field(
        foreign_key="tenantplan.id", primary_key=True, ondelete="CASCADE"
    )
    menu_id: uuid.UUID = Field(
        foreign_key="menu.id", primary_key=True, ondelete="CASCADE"
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class TenantPlanMenuUpdate(SQLModel):
    menu_ids: list[uuid.UUID]


class ModuleRegistry(SQLModel, table=True):
    code: str = Field(primary_key=True, max_length=100)
    version: str = Field(max_length=100)
    desired_state: ModuleDesiredState = Field(
        default=ModuleDesiredState.ENABLED, sa_type=String(32), index=True
    )
    observed_state: ModuleObservedState = Field(
        default=ModuleObservedState.BUNDLED, sa_type=String(32), index=True
    )
    manifest_digest: str = Field(max_length=100)
    target_revision: str | None = Field(default=None, max_length=100)
    actual_revision: str | None = Field(default=None, max_length=100)
    health_details: str | None = Field(default=None, max_length=4000)
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class ModuleRegistryPublic(SQLModel):
    code: str
    version: str
    desired_state: ModuleDesiredState
    observed_state: ModuleObservedState
    manifest_digest: str
    target_revision: str | None = None
    actual_revision: str | None = None
    health_details: str | None = None
    updated_at: datetime | None = None


class ModuleDesiredStateUpdate(SQLModel):
    desired_state: ModuleDesiredState
    reason: str | None = Field(default=None, max_length=500)


class TenantPlanModule(SQLModel, table=True):
    plan_id: uuid.UUID = Field(
        foreign_key="tenantplan.id", primary_key=True, ondelete="CASCADE"
    )
    module_code: str = Field(primary_key=True, max_length=100)
    is_enabled: bool = True
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class TenantPlanModuleUpdate(SQLModel):
    is_enabled: bool


class TenantModule(SQLModel, table=True):
    tenant_id: uuid.UUID = Field(
        foreign_key="tenant.id", primary_key=True, ondelete="CASCADE"
    )
    module_code: str = Field(primary_key=True, max_length=100)
    is_enabled: bool = True
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class TenantModuleUpdate(SQLModel):
    is_enabled: bool


class TenantModuleEntitlementOverride(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        foreign_key="tenant.id", index=True, ondelete="CASCADE"
    )
    module_code: str = Field(max_length=100, index=True)
    effect: ModuleEntitlementEffect = Field(sa_type=String(32))
    starts_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True), index=True  # type: ignore
    )
    ends_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True), index=True  # type: ignore
    )
    reason: str = Field(min_length=1, max_length=500)
    operator_user_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class TenantModuleEntitlementOverrideCreate(SQLModel):
    effect: ModuleEntitlementEffect
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    reason: str = Field(min_length=1, max_length=500)


class ModuleStateAudit(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    module_code: str = Field(max_length=100, index=True)
    tenant_id: uuid.UUID | None = Field(
        default=None, foreign_key="tenant.id", index=True, ondelete="CASCADE"
    )
    action: str = Field(max_length=100)
    previous_value: str | None = Field(default=None, max_length=100)
    next_value: str | None = Field(default=None, max_length=100)
    reason: str | None = Field(default=None, max_length=500)
    actor_user_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class OutboxEvent(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    module_code: str = Field(max_length=100, index=True)
    event_type: str = Field(max_length=200, index=True)
    event_version: int = 1
    tenant_id: uuid.UUID | None = Field(
        default=None, foreign_key="tenant.id", index=True, ondelete="CASCADE"
    )
    aggregate_id: str = Field(max_length=100, index=True)
    payload: str = Field(max_length=16000)
    trace_id: str | None = Field(default=None, max_length=100)
    occurred_at: datetime = Field(sa_type=DateTime(timezone=True))  # type: ignore
    available_at: datetime = Field(sa_type=DateTime(timezone=True), index=True)  # type: ignore
    status: OutboxEventStatus = Field(
        default=OutboxEventStatus.PENDING, sa_type=String(32), index=True
    )
    attempts: int = 0
    last_error: str | None = Field(default=None, max_length=2000)
    published_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)  # type: ignore
    )
    dead_lettered_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)  # type: ignore
    )


class EventConsumerReceipt(SQLModel, table=True):
    consumer_name: str = Field(primary_key=True, max_length=100)
    event_id: uuid.UUID = Field(
        foreign_key="outboxevent.id", primary_key=True, ondelete="CASCADE"
    )
    processed_at: datetime = Field(sa_type=DateTime(timezone=True))  # type: ignore


class CapabilityBinding(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "consumer_module",
            "aggregate_type",
            "aggregate_id",
            "capability_code",
            name="uq_capability_binding_aggregate",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        foreign_key="tenant.id", index=True, ondelete="CASCADE"
    )
    consumer_module: str = Field(max_length=100, index=True)
    aggregate_type: str = Field(max_length=100)
    aggregate_id: str = Field(max_length=100)
    capability_code: str = Field(max_length=200)
    provider_code: str = Field(max_length=100)
    provider_version: str = Field(max_length=100)
    external_instance_id: str | None = Field(default=None, max_length=200)
    status: CapabilityBindingStatus = Field(
        default=CapabilityBindingStatus.ACTIVE, sa_type=String(32), index=True
    )
    created_at: datetime = Field(sa_type=DateTime(timezone=True))  # type: ignore
    closed_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)  # type: ignore
    )


class OutboxEventPublic(SQLModel):
    id: uuid.UUID
    module_code: str
    event_type: str
    event_version: int
    tenant_id: uuid.UUID | None = None
    aggregate_id: str
    occurred_at: datetime
    status: OutboxEventStatus
    attempts: int
    last_error: str | None = None


# Global user identity properties
class UserIdentityBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    mobile: str | None = Field(default=None, unique=True, index=True, max_length=32)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)
    avatar_url: str | None = Field(default=None, max_length=500)


class UserBase(UserIdentityBase):
    department_id: uuid.UUID | None = None


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    mobile: str | None = Field(default=None, max_length=32)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class SmsCodeRequest(SQLModel):
    tenant_code: str = Field(min_length=1, max_length=100)
    mobile: str = Field(min_length=11, max_length=32)
    scene: Literal["login", "register"] = "login"


class SmsCodeSent(SQLModel):
    message: str
    retry_after_seconds: int
    debug_code: str | None = None


class SmsLoginRequest(SQLModel):
    tenant_code: str = Field(min_length=1, max_length=100)
    mobile: str = Field(min_length=11, max_length=32)
    code: str = Field(min_length=6, max_length=6)


class RegistrationStatus(SQLModel):
    enabled: bool


class QrCodeLoginCreate(SQLModel):
    tenant_code: str = Field(min_length=1, max_length=100)


class QrCodeLoginChallenge(SQLModel):
    challenge_id: uuid.UUID
    scan_token: str
    poll_token: str
    expires_in: int


class QrCodeLoginStatusRequest(SQLModel):
    challenge_id: uuid.UUID
    poll_token: str = Field(min_length=32, max_length=255)


class QrCodeLoginStatus(SQLModel):
    status: Literal["pending", "confirmed"]
    expires_in: int


class QrCodeLoginConfirmRequest(SQLModel):
    challenge_id: uuid.UUID
    scan_token: str = Field(min_length=32, max_length=255)


class QrCodeLoginConfirmResult(SQLModel):
    message: str
    tenant_name: str
    user_name: str


class QrCodeLoginExchangeRequest(SQLModel):
    challenge_id: uuid.UUID
    poll_token: str = Field(min_length=32, max_length=255)


class TenantRegistrationRequest(SQLModel):
    tenant_code: str = Field(min_length=3, max_length=32)
    tenant_name: str = Field(min_length=2, max_length=100)
    email: EmailStr = Field(max_length=255)
    mobile: str = Field(min_length=11, max_length=32)
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    sms_code: str = Field(min_length=6, max_length=6)


# Properties to receive via API on update, all are optional
class UserUpdate(SQLModel):
    email: EmailStr | None = Field(default=None, max_length=255)
    mobile: str | None = Field(default=None, max_length=32)
    is_active: bool | None = None
    is_superuser: bool | None = None
    full_name: str | None = Field(default=None, max_length=255)
    department_id: uuid.UUID | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class MasterDataAnonymizeRequest(SQLModel):
    reason: str = Field(min_length=1, max_length=500)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class UserMfaEnable(SQLModel):
    code: str = Field(min_length=6, max_length=16)


class UserMfaEnableResult(SQLModel):
    message: str
    recovery_codes: list[str]


class UserMfaDisable(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    code: str = Field(min_length=6, max_length=16)


# Database model, database table inferred from class name
class User(UserIdentityBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    mfa_enabled: bool = Field(default=False, nullable=False)
    mfa_secret_encrypted: str | None = Field(default=None, max_length=500)
    mfa_recovery_code_hashes: str | None = Field(default=None, max_length=2000)
    mfa_confirmed_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    archived_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True), index=True  # type: ignore
    )
    anonymized_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True), index=True  # type: ignore
    )


class TenantMembership(SQLModel, table=True):
    __table_args__ = (
        ForeignKeyConstraint(
            ["department_id", "tenant_id"],
            ["department.id", "department.tenant_id"],
            ondelete="RESTRICT",
        ),
    )

    user_id: uuid.UUID = Field(
        foreign_key="user.id", primary_key=True, ondelete="CASCADE"
    )
    tenant_id: uuid.UUID = Field(
        foreign_key="tenant.id", primary_key=True, index=True, ondelete="CASCADE"
    )
    department_id: uuid.UUID | None = Field(default=None, index=True)
    is_active: bool = True
    is_default: bool = False
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


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


class UserMfaStatus(SQLModel):
    enabled: bool
    pending_setup: bool = False
    method: str | None = None
    confirmed_at: datetime | None = None
    recovery_codes_remaining: int = 0


class UserMfaSetup(SQLModel):
    secret: str
    otpauth_uri: str
    issuer: str
    account_name: str


class DepartmentBase(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=100, index=True)
    parent_id: uuid.UUID | None = None
    leader_user_id: uuid.UUID | None = None
    sort: int = 0
    is_active: bool = True
    remark: str | None = Field(default=None, max_length=255)


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, min_length=1, max_length=100)
    parent_id: uuid.UUID | None = None
    leader_user_id: uuid.UUID | None = None
    sort: int | None = None
    is_active: bool | None = None
    remark: str | None = Field(default=None, max_length=255)


class Department(DepartmentBase, table=True):
    __table_args__ = (
        ForeignKeyConstraint(
            ["parent_id", "tenant_id"],
            ["department.id", "department.tenant_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["leader_user_id", "tenant_id"],
            ["tenantmembership.user_id", "tenantmembership.tenant_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("tenant_id", "code", name="uq_department_tenant_code"),
        UniqueConstraint("id", "tenant_id", name="uq_department_id_tenant_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        default=DEFAULT_TENANT_ID,
        foreign_key="tenant.id",
        index=True,
        ondelete="CASCADE",
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    archived_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True), index=True  # type: ignore
    )


class DepartmentPublic(DepartmentBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DepartmentsPublic(SQLModel):
    items: list[DepartmentPublic]
    total: int
    page: int
    page_size: int


class PostBase(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=100, index=True)
    sort: int = 0
    is_active: bool = True
    remark: str | None = Field(default=None, max_length=255)


class PostCreate(PostBase):
    pass


class PostUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, min_length=1, max_length=100)
    sort: int | None = None
    is_active: bool | None = None
    remark: str | None = Field(default=None, max_length=255)


class Post(PostBase, table=True):
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_post_tenant_code"),
        UniqueConstraint("id", "tenant_id", name="uq_post_id_tenant_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        default=DEFAULT_TENANT_ID,
        foreign_key="tenant.id",
        index=True,
        ondelete="CASCADE",
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    archived_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True), index=True  # type: ignore
    )


class PostPublic(PostBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PostsPublic(SQLModel):
    items: list[PostPublic]
    total: int
    page: int
    page_size: int


class UserPost(SQLModel, table=True):
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "tenant_id"],
            ["tenantmembership.user_id", "tenantmembership.tenant_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["post_id", "tenant_id"],
            ["post.id", "post.tenant_id"],
            ondelete="CASCADE",
        ),
    )

    user_id: uuid.UUID = Field(primary_key=True)
    post_id: uuid.UUID = Field(primary_key=True)
    tenant_id: uuid.UUID = Field(
        default=DEFAULT_TENANT_ID, primary_key=True, index=True
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class UserRole(SQLModel, table=True):
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "tenant_id"],
            ["tenantmembership.user_id", "tenantmembership.tenant_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["role_id", "tenant_id"],
            ["role.id", "role.tenant_id"],
            ondelete="CASCADE",
        ),
    )

    user_id: uuid.UUID = Field(primary_key=True)
    role_id: uuid.UUID = Field(primary_key=True)
    tenant_id: uuid.UUID = Field(
        default=DEFAULT_TENANT_ID, primary_key=True, index=True
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
    code: str = Field(min_length=1, max_length=100, index=True)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    sort: int = 0
    is_active: bool = True
    is_system: bool = False
    data_scope: DataScope = Field(default=DataScope.SELF, sa_type=String(32))


class RoleCreate(RoleBase):
    custom_department_ids: list[uuid.UUID] = Field(default_factory=list)


class RoleUpdate(SQLModel):
    code: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    sort: int | None = None
    is_active: bool | None = None
    is_system: bool | None = None
    data_scope: DataScope | None = None
    custom_department_ids: list[uuid.UUID] | None = None


class Role(RoleBase, table=True):
    __table_args__ = (
        CheckConstraint(
            "data_scope IN ('all', 'department', 'department_and_children', 'self', 'custom')",
            name="ck_role_data_scope",
        ),
        UniqueConstraint("tenant_id", "code", name="uq_role_tenant_code"),
        UniqueConstraint("id", "tenant_id", name="uq_role_id_tenant_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        default=DEFAULT_TENANT_ID,
        foreign_key="tenant.id",
        index=True,
        nullable=False,
        ondelete="CASCADE",
    )
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
    tenant_id: uuid.UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None
    custom_department_ids: list[uuid.UUID] = Field(default_factory=list)


class RolesPublic(SQLModel):
    items: list[RolePublic]
    total: int
    page: int
    page_size: int


class RoleMenuUpdate(SQLModel):
    menu_ids: list[uuid.UUID]


class RoleDataScopeDepartment(SQLModel, table=True):
    __table_args__ = (
        ForeignKeyConstraint(
            ["role_id", "tenant_id"],
            ["role.id", "role.tenant_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["department_id", "tenant_id"],
            ["department.id", "department.tenant_id"],
            ondelete="CASCADE",
        ),
    )

    role_id: uuid.UUID = Field(primary_key=True)
    department_id: uuid.UUID = Field(primary_key=True)
    tenant_id: uuid.UUID = Field(primary_key=True, index=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class UserRoleUpdate(SQLModel):
    role_ids: list[uuid.UUID]


class UserPostUpdate(SQLModel):
    post_ids: list[uuid.UUID]


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
    code: str = Field(min_length=1, max_length=100, index=True)
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
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_dictionarytype_tenant_code"),
        UniqueConstraint("id", "tenant_id", name="uq_dictionarytype_id_tenant_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        default=DEFAULT_TENANT_ID,
        foreign_key="tenant.id",
        index=True,
        ondelete="CASCADE",
    )
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
    tenant_id: uuid.UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DictionaryTypesPublic(SQLModel):
    items: list[DictionaryTypePublic]
    total: int
    page: int
    page_size: int


class DictionaryItemBase(SQLModel):
    type_id: uuid.UUID
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
    __table_args__ = (
        ForeignKeyConstraint(
            ["type_id", "tenant_id"],
            ["dictionarytype.id", "dictionarytype.tenant_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "tenant_id",
            "type_id",
            "value",
            name="uq_dictionaryitem_tenant_type_value",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        default=DEFAULT_TENANT_ID,
        foreign_key="tenant.id",
        index=True,
        ondelete="CASCADE",
    )
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
    tenant_id: uuid.UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DictionaryItemsPublic(SQLModel):
    items: list[DictionaryItemPublic]
    total: int
    page: int
    page_size: int


class SystemSettingBase(SQLModel):
    key: str = Field(min_length=1, max_length=100, index=True)
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
    __table_args__ = (
        UniqueConstraint("tenant_id", "key", name="uq_systemsetting_tenant_key"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        default=DEFAULT_TENANT_ID,
        foreign_key="tenant.id",
        index=True,
        ondelete="CASCADE",
    )
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
    tenant_id: uuid.UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SystemSettingsPublic(SQLModel):
    items: list[SystemSettingPublic]
    total: int
    page: int
    page_size: int


class LoginLogBase(SQLModel):
    user_id: uuid.UUID | None = None
    email: str | None = Field(default=None, max_length=255, index=True)
    ip: str | None = Field(default=None, max_length=100)
    user_agent: str | None = Field(default=None, max_length=500)
    status: str = Field(max_length=20)
    failure_reason: str | None = Field(default=None, max_length=255)


class LoginLog(LoginLogBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        default=DEFAULT_TENANT_ID,
        foreign_key="tenant.id",
        index=True,
        ondelete="CASCADE",
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        index=True,
    )


class LoginLogPublic(LoginLogBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime | None = None


class LoginLogsPublic(SQLModel):
    items: list[LoginLogPublic]
    total: int
    page: int
    page_size: int


class UserSession(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        foreign_key="user.id", index=True, nullable=False, ondelete="CASCADE"
    )
    tenant_id: uuid.UUID = Field(
        foreign_key="tenant.id", index=True, nullable=False, ondelete="RESTRICT"
    )
    token_jti: str = Field(max_length=64, unique=True, index=True)
    ip: str | None = Field(default=None, max_length=100)
    user_agent: str | None = Field(default=None, max_length=500)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    last_active_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    expires_at: datetime = Field(sa_type=DateTime(timezone=True))  # type: ignore
    revoked_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore


class OAuth2ClientBase(SQLModel):
    client_id: str = Field(min_length=1, max_length=100, unique=True, index=True)
    client_secret: str | None = Field(default=None, max_length=500)
    name: str = Field(min_length=1, max_length=100)
    logo: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=500)
    access_token_validity_seconds: int = Field(default=7200, ge=60)
    refresh_token_validity_seconds: int = Field(default=2_592_000, ge=60)
    authorized_grant_types: str = Field(
        default="authorization_code,refresh_token", max_length=500
    )
    scopes: str | None = Field(default="read,write", max_length=500)
    auto_approve_scopes: str | None = Field(default=None, max_length=500)
    redirect_uris: str | None = Field(default=None, max_length=1000)
    authorities: str | None = Field(default=None, max_length=500)
    resource_ids: str | None = Field(default=None, max_length=500)
    additional_information: str | None = Field(default=None, max_length=2000)
    is_active: bool = True


class OAuth2Client(OAuth2ClientBase, table=True):
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "client_id",
            name="uq_oauth2client_tenant_client_id",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_oauth2client_id_tenant_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        default=DEFAULT_TENANT_ID,
        foreign_key="tenant.id",
        index=True,
        ondelete="CASCADE",
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class OAuth2ClientCreate(OAuth2ClientBase):
    pass


class OAuth2ClientUpdate(SQLModel):
    current_password: str | None = Field(default=None, min_length=8, max_length=128)
    client_id: str | None = Field(default=None, min_length=1, max_length=100)
    client_secret: str | None = Field(default=None, max_length=500)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    logo: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=500)
    access_token_validity_seconds: int | None = Field(default=None, ge=60)
    refresh_token_validity_seconds: int | None = Field(default=None, ge=60)
    authorized_grant_types: str | None = Field(default=None, max_length=500)
    scopes: str | None = Field(default=None, max_length=500)
    auto_approve_scopes: str | None = Field(default=None, max_length=500)
    redirect_uris: str | None = Field(default=None, max_length=1000)
    authorities: str | None = Field(default=None, max_length=500)
    resource_ids: str | None = Field(default=None, max_length=500)
    additional_information: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class OAuth2ClientPublic(OAuth2ClientBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    client_secret: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class OAuth2ClientsPublic(SQLModel):
    items: list[OAuth2ClientPublic]
    total: int
    page: int
    page_size: int


class OAuth2AccessToken(SQLModel, table=True):
    __table_args__ = (
        ForeignKeyConstraint(
            ["client_id", "tenant_id"],
            ["oauth2client.client_id", "oauth2client.tenant_id"],
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        default=DEFAULT_TENANT_ID,
        foreign_key="tenant.id",
        index=True,
        ondelete="CASCADE",
    )
    access_token: str | None = Field(
        default=None, max_length=500, unique=True, index=True
    )
    refresh_token: str | None = Field(default=None, max_length=500, index=True)
    access_token_hash: str | None = Field(
        default=None, max_length=128, unique=True, index=True
    )
    refresh_token_hash: str | None = Field(default=None, max_length=128, index=True)
    refresh_expires_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    token_family_id: uuid.UUID | None = Field(default=None, index=True)
    user_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", index=True, ondelete="SET NULL"
    )
    user_email: str | None = Field(default=None, max_length=255)
    user_full_name: str | None = Field(default=None, max_length=255)
    client_id: str = Field(max_length=100, index=True)
    scopes: str | None = Field(default=None, max_length=500)
    expires_at: datetime = Field(sa_type=DateTime(timezone=True))  # type: ignore
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    revoked_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore


class OAuth2AccessTokenPublic(SQLModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    access_token: str | None = None
    refresh_token: str | None = None
    user_id: uuid.UUID | None = None
    user_email: str | None = None
    user_full_name: str | None = None
    client_id: str
    scopes: str | None = None
    expires_at: datetime
    created_at: datetime | None = None
    revoked_at: datetime | None = None


class OAuth2AccessTokensPublic(SQLModel):
    items: list[OAuth2AccessTokenPublic]
    total: int
    page: int
    page_size: int


class OAuth2AuthorizationCode(SQLModel, table=True):
    __table_args__ = (
        ForeignKeyConstraint(
            ["client_id", "tenant_id"],
            ["oauth2client.client_id", "oauth2client.tenant_id"],
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        default=DEFAULT_TENANT_ID,
        foreign_key="tenant.id",
        index=True,
        ondelete="CASCADE",
    )
    code_hash: str = Field(max_length=128, unique=True, index=True)
    client_id: str = Field(max_length=100, index=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    redirect_uri: str = Field(max_length=1000)
    scopes: str | None = Field(default=None, max_length=500)
    code_challenge: str = Field(max_length=128)
    code_challenge_method: str = Field(default="S256", max_length=10)
    expires_at: datetime = Field(sa_type=DateTime(timezone=True))  # type: ignore
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    used_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore


class EnterpriseOidcAuthorizationState(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    state_hash: str = Field(max_length=128, unique=True, index=True)
    code_verifier: str = Field(max_length=128)
    nonce: str = Field(max_length=128)
    expires_at: datetime = Field(sa_type=DateTime(timezone=True))  # type: ignore
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    consumed_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore


class EnterpriseOidcIdentity(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "provider", "subject", name="uq_enterpriseoidcidentity_provider_subject"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    provider: str = Field(default="enterprise_oidc", max_length=100)
    subject: str = Field(max_length=500)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class EnterpriseOidcLoginTicket(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    ticket_hash: str = Field(max_length=128, unique=True, index=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    expires_at: datetime = Field(sa_type=DateTime(timezone=True))  # type: ignore
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    consumed_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore


class EnterpriseOidcStatus(SQLModel):
    enabled: bool
    login_url: str | None = None


class EnterpriseOidcTicketExchange(SQLModel):
    ticket: str = Field(min_length=32, max_length=500)


class SocialClientBase(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    social_type: str = Field(min_length=1, max_length=50, index=True)
    user_type: str = Field(default="admin", max_length=50)
    client_id: str = Field(min_length=1, max_length=255)
    client_secret: str | None = Field(default=None, max_length=500)
    agent_id: str | None = Field(default=None, max_length=100)
    is_active: bool = True
    remark: str | None = Field(default=None, max_length=255)


class SocialClient(SocialClientBase, table=True):
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "social_type",
            "user_type",
            name="uq_socialclient_tenant_social_type_user_type",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_socialclient_id_tenant_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        default=DEFAULT_TENANT_ID,
        foreign_key="tenant.id",
        index=True,
        ondelete="CASCADE",
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class SocialClientCreate(SocialClientBase):
    pass


class SocialClientUpdate(SQLModel):
    current_password: str | None = Field(default=None, min_length=8, max_length=128)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    social_type: str | None = Field(default=None, min_length=1, max_length=50)
    user_type: str | None = Field(default=None, max_length=50)
    client_id: str | None = Field(default=None, min_length=1, max_length=255)
    client_secret: str | None = Field(default=None, max_length=500)
    agent_id: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None
    remark: str | None = Field(default=None, max_length=255)


class SocialClientPublic(SocialClientBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    client_secret: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SocialClientsPublic(SQLModel):
    items: list[SocialClientPublic]
    total: int
    page: int
    page_size: int


class SocialUser(SQLModel, table=True):
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "tenant_id"],
            ["tenantmembership.user_id", "tenantmembership.tenant_id"],
        ),
        ForeignKeyConstraint(
            ["social_client_id", "tenant_id"],
            ["socialclient.id", "socialclient.tenant_id"],
        ),
        UniqueConstraint(
            "tenant_id",
            "type",
            "openid",
            name="uq_socialuser_tenant_type_openid",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        default=DEFAULT_TENANT_ID,
        foreign_key="tenant.id",
        index=True,
        ondelete="CASCADE",
    )
    type: str = Field(max_length=50, index=True)
    openid: str = Field(max_length=255, index=True)
    unionid: str | None = Field(default=None, max_length=255)
    nickname: str | None = Field(default=None, max_length=255)
    avatar: str | None = Field(default=None, max_length=500)
    token: str | None = Field(default=None, max_length=1000)
    raw_token_info: str | None = Field(default=None, max_length=4000)
    raw_user_info: str | None = Field(default=None, max_length=4000)
    code: str | None = Field(default=None, max_length=255)
    state: str | None = Field(default=None, max_length=255)
    user_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", index=True, ondelete="SET NULL"
    )
    social_client_id: uuid.UUID | None = Field(
        default=None, foreign_key="socialclient.id", index=True, ondelete="SET NULL"
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class SocialUserPublic(SQLModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    type: str
    openid: str
    unionid: str | None = None
    nickname: str | None = None
    avatar: str | None = None
    token: str | None = None
    raw_token_info: str | None = None
    raw_user_info: str | None = None
    code: str | None = None
    state: str | None = None
    user_id: uuid.UUID | None = None
    social_client_id: uuid.UUID | None = None
    user_email: str | None = None
    user_full_name: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SocialUsersPublic(SQLModel):
    items: list[SocialUserPublic]
    total: int
    page: int
    page_size: int


class SocialUserBind(SQLModel):
    user_id: uuid.UUID


class OperationLogBase(SQLModel):
    user_id: uuid.UUID | None = Field(default=None, index=True)
    email: str | None = Field(default=None, max_length=255)
    module: str = Field(max_length=100)
    action: str = Field(max_length=100)
    method: str = Field(max_length=20)
    path: str = Field(max_length=500, index=True)
    status_code: int
    duration_ms: int
    ip: str | None = Field(default=None, max_length=100)
    user_agent: str | None = Field(default=None, max_length=500)
    request_summary: str | None = Field(default=None, max_length=1000)
    response_summary: str | None = Field(default=None, max_length=1000)


class OperationLog(OperationLogBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        default=DEFAULT_TENANT_ID,
        foreign_key="tenant.id",
        index=True,
        ondelete="CASCADE",
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        index=True,
    )


class OperationLogPublic(OperationLogBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
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
    uploader_id: uuid.UUID | None = Field(default=None, index=True)
    is_public: bool = False


class FileAsset(FileAssetBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        default=DEFAULT_TENANT_ID,
        foreign_key="tenant.id",
        index=True,
        ondelete="CASCADE",
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        index=True,
    )


class FileAssetPublic(FileAssetBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime | None = None


class FileAssetsPublic(SQLModel):
    items: list[FileAssetPublic]
    total: int
    page: int
    page_size: int


class FileStorageChannelBase(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=100, index=True)
    provider: str = Field(default="local", max_length=50)
    endpoint_url: str | None = Field(default=None, max_length=500)
    region: str | None = Field(default=None, max_length=100)
    bucket: str | None = Field(default=None, max_length=255)
    access_key_id: str | None = Field(default=None, max_length=255)
    secret_access_key: str | None = Field(default=None, max_length=500)
    object_prefix: str | None = Field(default=None, max_length=255)
    addressing_style: str = Field(default="auto", max_length=20)
    auto_create_bucket: bool = False
    is_default: bool = False
    is_active: bool = True
    remark: str | None = Field(default=None, max_length=255)


class FileStorageChannel(FileStorageChannelBase, table=True):
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "code",
            name="uq_filestoragechannel_tenant_code",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        default=DEFAULT_TENANT_ID,
        foreign_key="tenant.id",
        index=True,
        ondelete="CASCADE",
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class FileStorageChannelCreate(FileStorageChannelBase):
    pass


class FileStorageChannelUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, min_length=1, max_length=100)
    provider: str | None = Field(default=None, max_length=50)
    endpoint_url: str | None = Field(default=None, max_length=500)
    region: str | None = Field(default=None, max_length=100)
    bucket: str | None = Field(default=None, max_length=255)
    access_key_id: str | None = Field(default=None, max_length=255)
    secret_access_key: str | None = Field(default=None, max_length=500)
    object_prefix: str | None = Field(default=None, max_length=255)
    addressing_style: str | None = Field(default=None, max_length=20)
    auto_create_bucket: bool | None = None
    is_default: bool | None = None
    is_active: bool | None = None
    remark: str | None = Field(default=None, max_length=255)


class FileStorageChannelPublic(FileStorageChannelBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    secret_access_key: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FileStorageChannelsPublic(SQLModel):
    items: list[FileStorageChannelPublic]
    total: int
    page: int
    page_size: int


class FileDownloadUrl(SQLModel):
    url: str
    expires_in: int | None = None


class StorageConfigPublic(SQLModel):
    provider: str
    channel_id: uuid.UUID | None = None
    channel_name: str | None = None
    max_size_mb: int
    allowed_extensions: str
    default_public: bool = False
    s3_bucket: str | None = None
    s3_endpoint_url: str | None = None
    presigned_url_expire_seconds: int | None = None


class UploadConfigPublic(SQLModel):
    max_size_mb: int
    allowed_extensions: str
    default_public: bool
    presigned_url_expire_seconds: int


class UploadConfigUpdate(SQLModel):
    max_size_mb: int | None = Field(default=None, ge=1, le=1024)
    allowed_extensions: str | None = Field(default=None, max_length=1000)
    default_public: bool | None = None
    presigned_url_expire_seconds: int | None = Field(default=None, ge=60, le=86_400)


class SmsChannelBase(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=100, index=True)
    provider: str = Field(default="debug", max_length=50)
    signature: str = Field(min_length=1, max_length=100)
    api_key: str | None = Field(default=None, max_length=500)
    api_secret: str | None = Field(default=None, max_length=500)
    callback_url: str | None = Field(default=None, max_length=500)
    is_default: bool = False
    is_active: bool = True
    remark: str | None = Field(default=None, max_length=255)


class SmsChannel(SmsChannelBase, table=True):
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_smschannel_tenant_code"),
        UniqueConstraint("id", "tenant_id", name="uq_smschannel_id_tenant_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        default=DEFAULT_TENANT_ID,
        foreign_key="tenant.id",
        index=True,
        ondelete="CASCADE",
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class SmsChannelCreate(SmsChannelBase):
    pass


class SmsChannelUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, min_length=1, max_length=100)
    provider: str | None = Field(default=None, max_length=50)
    signature: str | None = Field(default=None, min_length=1, max_length=100)
    api_key: str | None = Field(default=None, max_length=500)
    api_secret: str | None = Field(default=None, max_length=500)
    callback_url: str | None = Field(default=None, max_length=500)
    is_default: bool | None = None
    is_active: bool | None = None
    remark: str | None = Field(default=None, max_length=255)


class SmsChannelPublic(SmsChannelBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    api_secret: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SmsChannelsPublic(SQLModel):
    items: list[SmsChannelPublic]
    total: int
    page: int
    page_size: int


class SmsTemplateBase(SQLModel):
    type: str = Field(default="notification", max_length=50)
    code: str = Field(min_length=1, max_length=100, index=True)
    name: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=1000)
    remark: str | None = Field(default=None, max_length=255)
    api_template_id: str | None = Field(default=None, max_length=100)
    channel_id: uuid.UUID | None = Field(default=None, index=True)
    channel_code: str | None = Field(default=None, max_length=100)
    is_active: bool = True


class SmsTemplate(SmsTemplateBase, table=True):
    __table_args__ = (
        ForeignKeyConstraint(
            ["channel_id", "tenant_id"],
            ["smschannel.id", "smschannel.tenant_id"],
        ),
        UniqueConstraint("tenant_id", "code", name="uq_smstemplate_tenant_code"),
        UniqueConstraint("id", "tenant_id", name="uq_smstemplate_id_tenant_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        default=DEFAULT_TENANT_ID,
        foreign_key="tenant.id",
        index=True,
        ondelete="CASCADE",
    )
    params: str = Field(default="", max_length=500)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class SmsTemplateCreate(SmsTemplateBase):
    pass


class SmsTemplateUpdate(SQLModel):
    type: str | None = Field(default=None, max_length=50)
    code: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    content: str | None = Field(default=None, min_length=1, max_length=1000)
    remark: str | None = Field(default=None, max_length=255)
    api_template_id: str | None = Field(default=None, max_length=100)
    channel_id: uuid.UUID | None = None
    is_active: bool | None = None


class SmsTemplatePublic(SmsTemplateBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    params: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SmsTemplatesPublic(SQLModel):
    items: list[SmsTemplatePublic]
    total: int
    page: int
    page_size: int


class SmsSendRequest(SQLModel):
    mobile: str = Field(min_length=6, max_length=32)
    template_params: dict[str, str] = Field(default_factory=dict)


class SmsDeliveryCallback(SQLModel):
    request_id: str = Field(min_length=1, max_length=100)
    status: str = Field(min_length=1, max_length=20)
    message: str | None = Field(default=None, max_length=1000)


class SmsLog(SQLModel, table=True):
    __table_args__ = (
        ForeignKeyConstraint(
            ["channel_id", "tenant_id"],
            ["smschannel.id", "smschannel.tenant_id"],
        ),
        ForeignKeyConstraint(
            ["template_id", "tenant_id"],
            ["smstemplate.id", "smstemplate.tenant_id"],
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        default=DEFAULT_TENANT_ID,
        foreign_key="tenant.id",
        index=True,
        ondelete="CASCADE",
    )
    channel_id: uuid.UUID | None = None
    channel_code: str | None = Field(default=None, max_length=100)
    template_id: uuid.UUID | None = None
    template_code: str | None = Field(default=None, max_length=100)
    template_name: str | None = Field(default=None, max_length=100)
    template_type: str | None = Field(default=None, max_length=50)
    template_content: str = Field(max_length=1000)
    template_params: str | None = Field(default=None, max_length=2000)
    api_template_id: str | None = Field(default=None, max_length=100)
    mobile: str = Field(max_length=32, index=True)
    send_status: str = Field(default="success", max_length=20)
    sent_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        index=True,
    )
    api_send_code: str | None = Field(default=None, max_length=100)
    api_send_message: str | None = Field(default=None, max_length=1000)
    api_request_id: str | None = Field(default=None, max_length=100, index=True)
    api_serial_no: str | None = Field(default=None, max_length=100)
    receive_status: str = Field(default="pending", max_length=20)
    received_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    api_receive_code: str | None = Field(default=None, max_length=100)
    api_receive_message: str | None = Field(default=None, max_length=1000)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        index=True,
    )


class SmsLogPublic(SQLModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    channel_id: uuid.UUID | None = None
    channel_code: str | None = None
    template_id: uuid.UUID | None = None
    template_code: str | None = None
    template_name: str | None = None
    template_type: str | None = None
    template_content: str
    template_params: str | None = None
    api_template_id: str | None = None
    mobile: str
    send_status: str
    sent_at: datetime | None = None
    api_send_code: str | None = None
    api_send_message: str | None = None
    api_request_id: str | None = None
    api_serial_no: str | None = None
    receive_status: str
    received_at: datetime | None = None
    api_receive_code: str | None = None
    api_receive_message: str | None = None
    created_at: datetime | None = None


class SmsLogsPublic(SQLModel):
    items: list[SmsLogPublic]
    total: int
    page: int
    page_size: int


class MailAccountBase(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=100, index=True)
    email: EmailStr = Field(max_length=255)
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, max_length=500)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=465, ge=1, le=65_535)
    ssl_enable: bool = True
    starttls_enable: bool = False
    is_default: bool = False
    is_active: bool = True
    remark: str | None = Field(default=None, max_length=255)


class MailAccount(MailAccountBase, table=True):
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_mailaccount_tenant_code"),
        UniqueConstraint("id", "tenant_id", name="uq_mailaccount_id_tenant_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        default=DEFAULT_TENANT_ID,
        foreign_key="tenant.id",
        index=True,
        ondelete="CASCADE",
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class MailAccountCreate(MailAccountBase):
    pass


class MailAccountUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, max_length=500)
    host: str | None = Field(default=None, min_length=1, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65_535)
    ssl_enable: bool | None = None
    starttls_enable: bool | None = None
    is_default: bool | None = None
    is_active: bool | None = None
    remark: str | None = Field(default=None, max_length=255)


class MailAccountPublic(MailAccountBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    password: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MailAccountsPublic(SQLModel):
    items: list[MailAccountPublic]
    total: int
    page: int
    page_size: int


class MailTemplateBase(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=100, index=True)
    account_id: uuid.UUID | None = Field(default=None, index=True)
    nickname: str | None = Field(default=None, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=20_000)
    is_active: bool = True
    remark: str | None = Field(default=None, max_length=255)


class MailTemplate(MailTemplateBase, table=True):
    __table_args__ = (
        ForeignKeyConstraint(
            ["account_id", "tenant_id"],
            ["mailaccount.id", "mailaccount.tenant_id"],
        ),
        UniqueConstraint("tenant_id", "code", name="uq_mailtemplate_tenant_code"),
        UniqueConstraint("id", "tenant_id", name="uq_mailtemplate_id_tenant_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        default=DEFAULT_TENANT_ID,
        foreign_key="tenant.id",
        index=True,
        ondelete="CASCADE",
    )
    account_code: str | None = Field(default=None, max_length=100)
    params: str = Field(default="", max_length=500)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class MailTemplateCreate(MailTemplateBase):
    pass


class MailTemplateUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, min_length=1, max_length=100)
    account_id: uuid.UUID | None = None
    nickname: str | None = Field(default=None, max_length=100)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = Field(default=None, min_length=1, max_length=20_000)
    is_active: bool | None = None
    remark: str | None = Field(default=None, max_length=255)


class MailTemplatePublic(MailTemplateBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    account_code: str | None = None
    params: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MailTemplatesPublic(SQLModel):
    items: list[MailTemplatePublic]
    total: int
    page: int
    page_size: int


class MailSendRequest(SQLModel):
    to_email: EmailStr
    template_params: dict[str, str] = Field(default_factory=dict)


class MailLog(SQLModel, table=True):
    __table_args__ = (
        ForeignKeyConstraint(
            ["account_id", "tenant_id"],
            ["mailaccount.id", "mailaccount.tenant_id"],
        ),
        ForeignKeyConstraint(
            ["template_id", "tenant_id"],
            ["mailtemplate.id", "mailtemplate.tenant_id"],
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        default=DEFAULT_TENANT_ID,
        foreign_key="tenant.id",
        index=True,
        ondelete="CASCADE",
    )
    account_id: uuid.UUID | None = None
    account_code: str | None = Field(default=None, max_length=100)
    account_name: str | None = Field(default=None, max_length=100)
    template_id: uuid.UUID | None = None
    template_code: str | None = Field(default=None, max_length=100)
    template_name: str | None = Field(default=None, max_length=100)
    from_email: str = Field(max_length=255)
    from_name: str | None = Field(default=None, max_length=100)
    to_email: str = Field(max_length=255, index=True)
    title: str = Field(max_length=255)
    content: str = Field(max_length=20_000)
    template_params: str | None = Field(default=None, max_length=4000)
    send_status: str = Field(default="pending", max_length=20)
    sent_at: datetime | None = Field(  # type: ignore
        default=None,
        sa_type=DateTime(timezone=True),
        index=True,
    )
    message_id: str | None = Field(default=None, max_length=255)
    send_code: str | None = Field(default=None, max_length=100)
    send_message: str | None = Field(default=None, max_length=2000)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        index=True,
    )


class MailLogPublic(SQLModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    account_id: uuid.UUID | None = None
    account_code: str | None = None
    account_name: str | None = None
    template_id: uuid.UUID | None = None
    template_code: str | None = None
    template_name: str | None = None
    from_email: str
    from_name: str | None = None
    to_email: str
    title: str
    content: str
    template_params: str | None = None
    send_status: str
    sent_at: datetime | None = None
    message_id: str | None = None
    send_code: str | None = None
    send_message: str | None = None
    created_at: datetime | None = None


class MailLogsPublic(SQLModel):
    items: list[MailLogPublic]
    total: int
    page: int
    page_size: int


class NoticeBase(SQLModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=10000)
    type: str = Field(default="notice", max_length=50)
    priority: int = 0
    status: str = Field(default="draft", max_length=20, index=True)
    published_at: datetime | None = Field(  # type: ignore
        default=None,
        sa_type=DateTime(timezone=True),
        index=True,
    )


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
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_notice_id_tenant_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        default=DEFAULT_TENANT_ID,
        foreign_key="tenant.id",
        index=True,
        ondelete="CASCADE",
    )
    created_by: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        index=True,
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class NoticePublic(NoticeBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    created_by: uuid.UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class NoticesPublic(SQLModel):
    items: list[NoticePublic]
    total: int
    page: int
    page_size: int


class UserMessageBase(SQLModel):
    user_id: uuid.UUID = Field(index=True)
    notice_id: uuid.UUID | None = Field(default=None, index=True)
    template_id: uuid.UUID | None = Field(
        default=None,
        index=True,
    )
    template_code: str | None = Field(default=None, max_length=100, index=True)
    template_name: str | None = Field(default=None, max_length=100)
    sender_name: str | None = Field(default=None, max_length=100)
    template_params: str | None = Field(default=None, max_length=4000)
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=10000)
    type: str = Field(default="notice", max_length=50)
    is_read: bool = False
    read_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore


class UserMessage(UserMessageBase, table=True):
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "tenant_id"],
            ["tenantmembership.user_id", "tenantmembership.tenant_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["notice_id", "tenant_id"],
            ["notice.id", "notice.tenant_id"],
        ),
        ForeignKeyConstraint(
            ["template_id", "tenant_id"],
            ["sitemessagetemplate.id", "sitemessagetemplate.tenant_id"],
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        default=DEFAULT_TENANT_ID,
        foreign_key="tenant.id",
        index=True,
        ondelete="CASCADE",
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        index=True,
    )


class UserMessagePublic(UserMessageBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime | None = None


class UserMessagesPublic(SQLModel):
    items: list[UserMessagePublic]
    total: int
    page: int
    page_size: int


class SiteMessageTemplateBase(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=100, index=True)
    sender_name: str = Field(default="系统通知", min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=10_000)
    type: str = Field(default="notification", max_length=50)
    is_active: bool = True
    remark: str | None = Field(default=None, max_length=255)


class SiteMessageTemplate(SiteMessageTemplateBase, table=True):
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "code",
            name="uq_sitemessagetemplate_tenant_code",
        ),
        UniqueConstraint(
            "id",
            "tenant_id",
            name="uq_sitemessagetemplate_id_tenant_id",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        default=DEFAULT_TENANT_ID,
        foreign_key="tenant.id",
        index=True,
        ondelete="CASCADE",
    )
    params: str = Field(default="", max_length=500)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class SiteMessageTemplateCreate(SiteMessageTemplateBase):
    pass


class SiteMessageTemplateUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, min_length=1, max_length=100)
    sender_name: str | None = Field(default=None, min_length=1, max_length=100)
    content: str | None = Field(default=None, min_length=1, max_length=10_000)
    type: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None
    remark: str | None = Field(default=None, max_length=255)


class SiteMessageTemplatePublic(SiteMessageTemplateBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    params: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SiteMessageTemplatesPublic(SQLModel):
    items: list[SiteMessageTemplatePublic]
    total: int
    page: int
    page_size: int


class SiteMessageSendRequest(SQLModel):
    user_id: uuid.UUID
    template_params: dict[str, str] = Field(default_factory=dict)


class SiteMessagePublic(UserMessagePublic):
    user_email: str | None = None
    user_full_name: str | None = None


class SiteMessagesPublic(SQLModel):
    items: list[SiteMessagePublic]
    total: int
    page: int
    page_size: int


class DashboardOverview(SQLModel):
    user_count: int
    user_total: int
    login_count: int
    login_total: int
    file_count: int
    file_total: int
    operation_count: int
    operation_total: int


class DashboardHourlyTrend(SQLModel):
    hour: str
    login_count: int
    operation_count: int


class DashboardMonthlyVisit(SQLModel):
    month: str
    count: int


class DashboardNamedValue(SQLModel):
    name: str
    value: int


class DashboardRadarSeries(SQLModel):
    name: str
    values: list[int]


class DashboardAnalytics(SQLModel):
    overview: DashboardOverview
    hourly_trends: list[DashboardHourlyTrend]
    monthly_visits: list[DashboardMonthlyVisit]
    device_radar: list[DashboardRadarSeries]
    login_sources: list[DashboardNamedValue]
    module_distribution: list[DashboardNamedValue]


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: uuid.UUID


class LoginCaptchaChallenge(SQLModel):
    captcha_id: str
    challenge_text: str
    expires_in: int


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None
    jti: str | None = None
    tenant_id: uuid.UUID | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class HealthDependencyStatus(SQLModel):
    status: str
    enabled: bool = True
    degraded: bool = False
    available: bool | None = None


class HealthStatus(SQLModel):
    ok: bool
    degraded: bool = False
    database: HealthDependencyStatus
    redis: HealthDependencyStatus
