from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter


@dataclass(frozen=True)
class CapabilityRequirement:
    """A capability consumed by a module without coupling to its provider."""

    code: str
    major_version: int
    required: bool = False


@dataclass(frozen=True)
class CapabilityProvision:
    code: str
    major_version: int


@dataclass(frozen=True)
class EventContract:
    event_type: str
    version: int


@dataclass(frozen=True)
class MigrationSpec:
    """Database structures and revision namespace owned by a module."""

    namespace: str
    schema: str
    owned_tables: tuple[str, ...] = ()
    minimum_platform_revision: str | None = None


@dataclass(frozen=True)
class LifecycleHooks:
    """Optional composition-root hooks; module code never mutates the registry directly."""

    on_startup: Callable[[], None] | None = None
    on_ready: Callable[[], None] | None = None
    on_disabled: Callable[[], None] | None = None
    health_check: Callable[[], dict[str, Any]] | None = None


@dataclass(frozen=True)
class ModuleDefinition:
    """The code-owned contract for a module that can be part of an edition."""

    code: str
    version: str
    dependencies: tuple[str, ...]
    routers: tuple[APIRouter, ...]
    api_prefix: str
    permission_prefix: str
    migration: MigrationSpec
    optional_capabilities: tuple[CapabilityRequirement, ...] = ()
    provided_capabilities: tuple[CapabilityProvision, ...] = ()
    event_publishers: tuple[EventContract, ...] = ()
    event_subscribers: tuple[EventContract, ...] = ()
    workers: tuple[str, ...] = ()
    schedules: tuple[str, ...] = ()
    reference_guards: tuple[str, ...] = ()
    menus: tuple[str, ...] = ()
    lifecycle: LifecycleHooks = field(default_factory=LifecycleHooks)
