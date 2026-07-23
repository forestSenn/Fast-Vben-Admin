from unittest.mock import MagicMock

from app.core.cache import CacheNamespace, redis_cache
from app.platform.bootstrap import init_db
from app.platform.bootstrap_rbac import (
    bind_role_menus,
    ensure_default_tenant_plan_menus,
)
from app.platform.core.authorization_models import Menu, Role, RoleMenu
from app.platform.core.tenancy_models import TenantPlan, TenantPlanMenu


def test_bootstrap_menu_bindings_deduplicate_repeated_menu_objects() -> None:
    session = MagicMock()
    session.exec.return_value.all.return_value = []
    menu = Menu(title="Shared permission", permission_code="example:read")
    plan = TenantPlan(code="default", name="Default", is_default=True)
    role = Role(code="admin", name="Admin")

    ensure_default_tenant_plan_menus(
        session=session,
        plan=plan,
        menus=[menu, menu],
    )

    plan_bindings = [
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], TenantPlanMenu)
    ]
    assert len(plan_bindings) == 1

    session.reset_mock()
    session.exec.return_value.all.return_value = []
    bind_role_menus(session=session, role=role, menus=[menu, menu])

    role_bindings = [
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], RoleMenu)
    ]
    assert len(role_bindings) == 1


def test_init_db_invalidates_access_caches(db, monkeypatch) -> None:
    invalidated: list[CacheNamespace] = []
    monkeypatch.setattr(redis_cache, "bump_namespace", invalidated.append)

    init_db(db)

    assert CacheNamespace.RBAC in invalidated
    assert CacheNamespace.MODULE_ACCESS in invalidated
