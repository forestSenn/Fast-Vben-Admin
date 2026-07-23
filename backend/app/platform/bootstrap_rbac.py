"""Tenant RBAC, membership, and default role bootstrap service."""

from sqlmodel import Session, delete, select

from app.platform.bootstrap_configuration import (
    seed_dictionaries,
    seed_mail_accounts,
    seed_settings,
    seed_site_message_templates,
    seed_sms_channels,
    seed_storage_channels,
)
from app.platform.bootstrap_navigation import seed_menus
from app.platform.core.authorization_models import (
    Department,
    Menu,
    Post,
    Role,
    RoleMenu,
    UserRole,
)
from app.platform.core.identity_models import User
from app.platform.core.tenancy_models import (
    Tenant,
    TenantInitializationTemplate,
    TenantMembership,
    TenantPlan,
    TenantPlanMenu,
)
from app.platform.tenant_uow import PlatformTenantUnitOfWork


def ensure_tenant_membership(
    *,
    session: Session,
    user: User,
    tenant: Tenant,
    is_default: bool = False,
) -> TenantMembership:
    membership = session.exec(
        select(TenantMembership).where(
            TenantMembership.user_id == user.id,
            TenantMembership.tenant_id == tenant.id,
        )
    ).first()
    if membership:
        if is_default and not membership.is_default:
            membership.is_default = True
            session.add(membership)
        return membership
    membership = TenantMembership(
        user_id=user.id,
        tenant_id=tenant.id,
        is_default=is_default,
    )
    session.add(membership)
    session.flush()
    return membership

def ensure_default_tenant_plan_menus(
    *, session: Session, plan: TenantPlan | None, menus: list[Menu]
) -> None:
    if plan is None or not plan.is_default:
        return
    existing_menu_ids = set(
        session.exec(
            select(TenantPlanMenu.menu_id).where(TenantPlanMenu.plan_id == plan.id)
        ).all()
    )
    for menu in menus:
        if (
            menu.id not in existing_menu_ids
            and not (menu.permission_code or "").startswith("platform:")
        ):
            session.add(TenantPlanMenu(plan_id=plan.id, menu_id=menu.id))
            existing_menu_ids.add(menu.id)


def ensure_department(
    *, session: Session, tenant: Tenant, code: str, name: str, sort: int
) -> Department:
    department = session.exec(
        select(Department).where(
            Department.tenant_id == tenant.id,
            Department.code == code,
        )
    ).first()
    if department:
        return department

    department = Department(
        tenant_id=tenant.id,
        code=code,
        name=name,
        sort=sort,
    )
    session.add(department)
    session.flush()
    return department


def ensure_role(
    *,
    session: Session,
    tenant: Tenant,
    code: str,
    name: str,
    description: str,
    sort: int,
    is_system: bool,
    data_scope: str,
) -> Role:
    role = session.exec(
        select(Role).where(Role.tenant_id == tenant.id, Role.code == code)
    ).first()
    if role:
        if role.data_scope != data_scope:
            role.data_scope = data_scope  # type: ignore[assignment]
            session.add(role)
        return role

    role = Role(
        tenant_id=tenant.id,
        code=code,
        name=name,
        description=description,
        sort=sort,
        is_system=is_system,
        data_scope=data_scope,
    )
    session.add(role)
    session.flush()
    return role


def provision_tenant_roles(
    *,
    session: Session,
    tenant: Tenant,
    template: TenantInitializationTemplate,
    owner: User | None = None,
    additional_owners: list[User] | None = None,
) -> tuple[Role, Role, Role]:
    with PlatformTenantUnitOfWork(session, tenant.id, privileged=True):
        roles = _provision_tenant_roles(
            session=session,
            tenant=tenant,
            template=template,
            owner=owner,
            additional_owners=additional_owners,
        )
        # UserRole is queued after the last helper flush.  Flush while the
        # tenant scope is active so a caller's prior scope cannot write it.
        session.flush()
        return roles


def _provision_tenant_roles(
    *,
    session: Session,
    tenant: Tenant,
    template: TenantInitializationTemplate,
    owner: User | None = None,
    additional_owners: list[User] | None = None,
) -> tuple[Role, Role, Role]:
    default_department = ensure_department(
        session=session,
        tenant=tenant,
        code=template.root_department_code,
        name=template.root_department_name,
        sort=0,
    )
    if template.seed_posts:
        seed_posts(session=session, tenant=tenant)
    if template.seed_dictionaries:
        seed_dictionaries(session=session, tenant=tenant)
    if template.seed_settings:
        seed_settings(session=session, tenant=tenant)
    if template.seed_storage_channels:
        seed_storage_channels(session=session, tenant=tenant)
    if template.seed_message_templates:
        seed_site_message_templates(session=session, tenant=tenant)
    if template.seed_sms_channels:
        seed_sms_channels(session=session, tenant=tenant)
    if template.seed_mail_accounts:
        seed_mail_accounts(session=session, tenant=tenant)
    super_admin = ensure_role(
        session=session,
        tenant=tenant,
        code="super_admin",
        name="超级管理员",
        description="租户内置超级管理员角色，拥有全部租户权限。",
        sort=0,
        is_system=True,
        data_scope="all",
    )
    admin = ensure_role(
        session=session,
        tenant=tenant,
        code="admin",
        name="系统管理员",
        description="可维护当前租户的系统管理数据。",
        sort=10,
        is_system=True,
        data_scope="all",
    )
    default_user = ensure_role(
        session=session,
        tenant=tenant,
        code="user",
        name="普通用户",
        description="当前租户的默认普通用户角色。",
        sort=100,
        is_system=True,
        data_scope="self",
    )
    menus = seed_menus(session=session)
    plan_menu_ids = set(
        session.exec(
            select(TenantPlanMenu.menu_id).where(
                TenantPlanMenu.plan_id == tenant.plan_id
            )
        ).all()
    )
    plan_menus = [
        menu
        for menu in menus
        if menu.id in plan_menu_ids
        and not (menu.permission_code or "").startswith("platform:")
    ]
    replace_role_menus(
        session=session,
        role=super_admin,
        menus=plan_menus,
    )
    replace_role_menus(
        session=session,
        role=admin,
        menus=[
            menu
            for menu in plan_menus
            if menu.permission_code
            and (
                menu.permission_code.startswith("system:")
                or menu.permission_code in {"dashboard:view", "personal:message:list"}
            )
            or menu.type == "directory"
        ],
    )
    replace_role_menus(
        session=session,
        role=default_user,
        menus=[
            menu
            for menu in plan_menus
            if menu.permission_code
            in {
                "dashboard:view",
                "personal:message:list",
                "business:item:list",
                "business:item:create",
                "business:item:update",
                "business:item:delete",
            }
        ],
    )
    owners = [user for user in [owner, *(additional_owners or [])] if user is not None]
    for tenant_owner in owners:
        membership = ensure_tenant_membership(
            session=session,
            user=tenant_owner,
            tenant=tenant,
            is_default=False,
        )
        if membership.department_id is None:
            membership.department_id = default_department.id
            session.add(membership)
        bind_user_role(session=session, user=tenant_owner, role=super_admin)
    return super_admin, admin, default_user


def ensure_post(
    *, session: Session, tenant: Tenant, code: str, name: str, sort: int
) -> Post:
    post = session.exec(
        select(Post).where(Post.tenant_id == tenant.id, Post.code == code)
    ).first()
    if post:
        return post

    post = Post(tenant_id=tenant.id, code=code, name=name, sort=sort)
    session.add(post)
    session.flush()
    return post

def seed_posts(*, session: Session, tenant: Tenant) -> None:
    ensure_post(session=session, tenant=tenant, code="manager", name="经理", sort=10)
    ensure_post(
        session=session,
        tenant=tenant,
        code="developer",
        name="开发工程师",
        sort=20,
    )
    ensure_post(
        session=session, tenant=tenant, code="operator", name="运营专员", sort=30
    )

def bind_role_menus(*, session: Session, role: Role, menus: list[Menu]) -> None:
    existing_menu_ids = {
        role_menu.menu_id
        for role_menu in session.exec(
            select(RoleMenu).where(RoleMenu.role_id == role.id)
        ).all()
    }
    for menu in menus:
        if menu.id not in existing_menu_ids:
            session.add(RoleMenu(role_id=role.id, menu_id=menu.id))
            existing_menu_ids.add(menu.id)


def replace_role_menus(*, session: Session, role: Role, menus: list[Menu]) -> None:
    session.exec(delete(RoleMenu).where(RoleMenu.role_id == role.id))
    for menu in menus:
        session.add(RoleMenu(role_id=role.id, menu_id=menu.id))


def sync_tenant_plan_role_menus(*, session: Session, tenant: Tenant) -> bool:
    with PlatformTenantUnitOfWork(session, tenant.id, privileged=True):
        return _sync_tenant_plan_role_menus(session=session, tenant=tenant)


def _sync_tenant_plan_role_menus(*, session: Session, tenant: Tenant) -> bool:
    plan_menu_ids = set(
        session.exec(
            select(TenantPlanMenu.menu_id).where(
                TenantPlanMenu.plan_id == tenant.plan_id
            )
        ).all()
    )
    allowed_menus = session.exec(
        select(Menu).where(Menu.id.in_(plan_menu_ids))
    ).all()
    allowed_menus = [
        menu
        for menu in allowed_menus
        if not (menu.permission_code or "").startswith("platform:")
    ]
    allowed_menu_ids = {menu.id for menu in allowed_menus}
    roles = session.exec(
        select(Role).where(
            Role.tenant_id == tenant.id,
            Role.code.in_(["super_admin", "admin", "user"]),
        )
    ).all()
    role_by_code = {role.code: role for role in roles}
    super_admin = role_by_code.get("super_admin")
    if super_admin is None:
        return False

    replace_role_menus(session=session, role=super_admin, menus=allowed_menus)
    for role_code in ("admin", "user"):
        role = role_by_code.get(role_code)
        if role is None:
            continue
        current_menu_ids = set(
            session.exec(
                select(RoleMenu.menu_id).where(RoleMenu.role_id == role.id)
            ).all()
        )
        retained_ids = current_menu_ids & allowed_menu_ids
        replace_role_menus(
            session=session,
            role=role,
            menus=[menu for menu in allowed_menus if menu.id in retained_ids],
        )
    return True


def bind_user_role(*, session: Session, user: User, role: Role) -> None:
    existing = session.exec(
        select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.role_id == role.id,
            UserRole.tenant_id == role.tenant_id,
        )
    ).first()
    if not existing:
        session.add(
            UserRole(
                user_id=user.id,
                role_id=role.id,
                tenant_id=role.tenant_id,
            )
        )
