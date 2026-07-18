from sqlmodel import Session, create_engine, delete, select

from app import crud
from app.core.config import settings
from app.core.tenancy import DEFAULT_TENANT_CODE, DEFAULT_TENANT_ID
from app.models import (
    Department,
    DictionaryItem,
    DictionaryType,
    FileStorageChannel,
    MailAccount,
    MailTemplate,
    Menu,
    Post,
    Role,
    RoleMenu,
    SiteMessageTemplate,
    SmsChannel,
    SmsTemplate,
    SystemSetting,
    Tenant,
    TenantInitializationTemplate,
    TenantMembership,
    TenantPlan,
    TenantPlanMenu,
    TenantPlanProfile,
    TenantProfile,
    User,
    UserCreate,
    UserRole,
    get_datetime_utc,
)

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


def init_db(session: Session) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, create
    # the tables un-commenting the next lines
    # from sqlmodel import SQLModel

    # This works because the models are already imported and registered from app.models
    # SQLModel.metadata.create_all(engine)

    default_plan = ensure_default_tenant_plan(session=session)
    default_template = ensure_default_tenant_template(session=session)
    default_tenant = ensure_default_tenant(
        session=session,
        plan=default_plan,
        template=default_template,
    )
    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        user = crud.create_user(session=session, user_create=user_in)

    ensure_tenant_membership(
        session=session,
        user=user,
        tenant=default_tenant,
        is_default=True,
    )

    seed_system_data(session=session, superuser=user, tenant=default_tenant)


def ensure_default_tenant_plan(*, session: Session) -> TenantPlan:
    plan = session.exec(select(TenantPlan).where(TenantPlan.code == "standard")).first()
    if plan is not None:
        ensure_tenant_plan_profile(session=session, plan=plan)
        return plan
    plan = TenantPlan(
        code="standard",
        name="Standard",
        description="Default unlimited plan.",
        is_default=True,
        is_active=True,
    )
    session.add(plan)
    session.flush()
    ensure_tenant_plan_profile(session=session, plan=plan)
    return plan


def ensure_default_tenant_template(*, session: Session) -> TenantInitializationTemplate:
    template = session.exec(
        select(TenantInitializationTemplate).where(
            TenantInitializationTemplate.code == "standard"
        )
    ).first()
    if template is not None:
        return template
    template = TenantInitializationTemplate(
        code="standard",
        name="Standard",
        description="Default full tenant initialization.",
        is_default=True,
        is_active=True,
    )
    session.add(template)
    session.flush()
    return template


def ensure_default_tenant(
    *,
    session: Session,
    plan: TenantPlan,
    template: TenantInitializationTemplate,
) -> Tenant:
    tenant = session.exec(
        select(Tenant).where(Tenant.code == DEFAULT_TENANT_CODE)
    ).first()
    if tenant:
        ensure_tenant_profile(session=session, tenant=tenant)
        return tenant
    tenant = Tenant(
        id=DEFAULT_TENANT_ID,
        code=DEFAULT_TENANT_CODE,
        name="Default Tenant",
        description="Tenant created for data that predates v2.0 multi-tenancy.",
        plan_id=plan.id,
        initialization_template_id=template.id,
    )
    session.add(tenant)
    session.flush()
    ensure_tenant_profile(session=session, tenant=tenant)
    return tenant


def ensure_tenant_profile(*, session: Session, tenant: Tenant) -> TenantProfile:
    profile = session.get(TenantProfile, tenant.id)
    if profile is not None:
        return profile
    profile = TenantProfile(tenant_id=tenant.id)
    session.add(profile)
    session.flush()
    return profile


def ensure_tenant_plan_profile(
    *, session: Session, plan: TenantPlan
) -> TenantPlanProfile:
    profile = session.get(TenantPlanProfile, plan.id)
    if profile is not None:
        return profile
    profile = TenantPlanProfile(plan_id=plan.id)
    session.add(profile)
    session.flush()
    return profile


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


def seed_system_data(*, session: Session, superuser: User, tenant: Tenant) -> None:
    default_department = ensure_department(
        session=session,
        tenant=tenant,
        code="headquarters",
        name="总部",
        sort=0,
    )
    superuser_membership = ensure_tenant_membership(
        session=session,
        user=superuser,
        tenant=tenant,
    )
    if superuser_membership.department_id is None:
        superuser_membership.department_id = default_department.id
        session.add(superuser_membership)

    super_admin = ensure_role(
        session=session,
        tenant=tenant,
        code="super_admin",
        name="超级管理员",
        description="内置超级管理员角色，拥有全部权限。",
        sort=0,
        is_system=True,
        data_scope="all",
    )
    admin = ensure_role(
        session=session,
        tenant=tenant,
        code="admin",
        name="系统管理员",
        description="可维护系统管理基础数据。",
        sort=10,
        is_system=True,
        data_scope="all",
    )
    default_user = ensure_role(
        session=session,
        tenant=tenant,
        code="user",
        name="普通用户",
        description="默认普通用户角色。",
        sort=100,
        is_system=True,
        data_scope="self",
    )

    seed_dictionaries(session=session, tenant=tenant)
    seed_posts(session=session, tenant=tenant)
    seed_settings(session=session, tenant=tenant)
    seed_storage_channels(session=session, tenant=tenant)
    seed_sms_channels(session=session, tenant=tenant)
    seed_mail_accounts(session=session, tenant=tenant)
    seed_site_message_templates(session=session, tenant=tenant)
    menus = seed_menus(session=session)
    bind_role_menus(
        session=session,
        role=super_admin,
        menus=[
            menu
            for menu in menus
            if not (menu.permission_code or "").startswith("platform:")
        ],
    )
    bind_role_menus(
        session=session,
        role=admin,
        menus=[
            menu
            for menu in menus
            if menu.permission_code
            and (
                menu.permission_code.startswith("system:")
                or menu.permission_code in {"dashboard:view", "personal:message:list"}
            )
            or menu.type == "directory"
        ],
    )
    bind_role_menus(
        session=session,
        role=default_user,
        menus=[
            menu
            for menu in menus
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
    bind_user_role(session=session, user=superuser, role=super_admin)
    session.commit()


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


def ensure_menu(
    *,
    session: Session,
    title: str,
    type: str,
    sort: int,
    parent_id=None,
    route_path: str | None = None,
    route_name: str | None = None,
    component: str | None = None,
    icon: str | None = None,
    permission_code: str | None = None,
    is_visible: bool = True,
    is_active: bool = True,
) -> Menu:
    menu = None
    if permission_code:
        menu = session.exec(
            select(Menu).where(Menu.permission_code == permission_code)
        ).first()
    elif route_path:
        menu = session.exec(select(Menu).where(Menu.route_path == route_path)).first()

    if menu:
        changed = False
        for field, value in {
            "title": title,
            "type": type,
            "parent_id": parent_id,
            "route_path": route_path,
            "route_name": route_name,
            "component": component,
            "icon": icon,
            "sort": sort,
            "is_visible": is_visible,
            "is_active": is_active,
        }.items():
            if value is not None and getattr(menu, field) != value:
                setattr(menu, field, value)
                changed = True
        if changed:
            session.add(menu)
            session.flush()
        return menu

    menu = Menu(
        title=title,
        type=type,
        parent_id=parent_id,
        route_path=route_path,
        route_name=route_name,
        component=component,
        icon=icon,
        permission_code=permission_code,
        sort=sort,
        is_visible=is_visible,
        is_active=is_active,
    )
    session.add(menu)
    session.flush()
    return menu


def seed_menus(*, session: Session) -> list[Menu]:
    remove_obsolete_menus(session=session)
    dashboard = ensure_menu(
        session=session,
        title="menu.dashboard",
        type="menu",
        route_path="/dashboard",
        route_name="Dashboard",
        component="#/views/dashboard/analytics/index.vue",
        icon="lucide:layout-dashboard",
        permission_code="dashboard:view",
        sort=0,
    )
    system = ensure_menu(
        session=session,
        title="menu.system",
        type="directory",
        route_path="/system",
        route_name="System",
        icon="lucide:settings",
        sort=10,
    )
    tenant_center = ensure_menu(
        session=session,
        title="menu.systemTenantCenter",
        type="directory",
        parent_id=system.id,
        route_path="/system/tenant-center",
        route_name="SystemTenantCenter",
        icon="lucide:building",
        sort=5,
    )
    basic_settings = ensure_menu(
        session=session,
        title="menu.infrastructure",
        type="directory",
        route_path="/basic-settings",
        route_name="BasicSettings",
        icon="lucide:settings-2",
        sort=15,
    )
    tenants = ensure_menu(
        session=session,
        title="menu.systemTenants",
        type="menu",
        parent_id=tenant_center.id,
        route_path="/system/tenants",
        route_name="SystemTenants",
        component="#/views/system/tenants/index.vue",
        icon="lucide:building-2",
        permission_code="platform:tenant:list",
        sort=10,
    )
    tenant_plans = ensure_menu(
        session=session,
        title="menu.systemTenantPlans",
        type="menu",
        parent_id=tenant_center.id,
        route_path="/system/tenant-plans",
        route_name="SystemTenantPlans",
        component="#/views/system/tenant-plans/index.vue",
        icon="lucide:package",
        permission_code="platform:plan:list",
        sort=20,
    )
    tenant_templates = ensure_menu(
        session=session,
        title="menu.systemTenantTemplates",
        type="menu",
        parent_id=tenant_center.id,
        route_path="/system/tenant-templates",
        route_name="SystemTenantTemplates",
        component="#/views/system/tenant-templates/index.vue",
        icon="lucide:layout-template",
        permission_code="platform:template:list",
        sort=30,
    )
    users = ensure_menu(
        session=session,
        title="menu.systemUsers",
        type="menu",
        parent_id=system.id,
        route_path="/system/users",
        route_name="SystemUsers",
        component="#/views/system/users/index.vue",
        icon="lucide:users",
        permission_code="system:user:list",
        sort=10,
    )
    roles = ensure_menu(
        session=session,
        title="menu.systemRoles",
        type="menu",
        parent_id=system.id,
        route_path="/system/roles",
        route_name="SystemRoles",
        component="#/views/system/roles/index.vue",
        icon="lucide:shield-check",
        permission_code="system:role:list",
        sort=20,
    )
    menus = ensure_menu(
        session=session,
        title="menu.systemMenus",
        type="menu",
        parent_id=system.id,
        route_path="/system/menus",
        route_name="SystemMenus",
        component="#/views/system/menus/index.vue",
        icon="lucide:menu",
        permission_code="system:menu:list",
        sort=30,
    )
    departments = ensure_menu(
        session=session,
        title="menu.systemDepartments",
        type="menu",
        parent_id=system.id,
        route_path="/system/departments",
        route_name="SystemDepartments",
        component="#/views/system/departments/index.vue",
        icon="lucide:building-2",
        permission_code="system:department:list",
        sort=40,
    )
    posts = ensure_menu(
        session=session,
        title="menu.systemPosts",
        type="menu",
        parent_id=system.id,
        route_path="/system/posts",
        route_name="SystemPosts",
        component="#/views/system/posts/index.vue",
        icon="lucide:briefcase-business",
        permission_code="system:post:list",
        sort=50,
    )
    dictionaries = ensure_menu(
        session=session,
        title="menu.systemDictionaries",
        type="menu",
        parent_id=system.id,
        route_path="/system/dictionaries",
        route_name="SystemDictionaries",
        component="#/views/system/dictionaries/index.vue",
        icon="lucide:book-open",
        permission_code="system:dict:list",
        sort=60,
    )
    system_settings = ensure_menu(
        session=session,
        title="menu.systemSettings",
        type="menu",
        parent_id=basic_settings.id,
        route_path="/basic-settings/settings",
        route_name="SystemSettings",
        component="#/views/system/settings/index.vue",
        icon="lucide:sliders-horizontal",
        permission_code="system:setting:list",
        sort=10,
    )
    oauth2 = ensure_menu(
        session=session,
        title="menu.oauth2",
        type="directory",
        parent_id=system.id,
        route_path="/system/oauth2",
        route_name="OAuth2",
        icon="lucide:shield",
        sort=85,
    )
    oauth2_clients = ensure_menu(
        session=session,
        title="menu.oauth2Clients",
        type="menu",
        parent_id=oauth2.id,
        route_path="/system/oauth2/clients",
        route_name="OAuth2Clients",
        component="#/views/oauth2/clients/index.vue",
        icon="lucide:hard-drive",
        permission_code="system:oauth2-client:list",
        sort=10,
    )
    oauth2_tokens = ensure_menu(
        session=session,
        title="menu.oauth2Tokens",
        type="menu",
        parent_id=oauth2.id,
        route_path="/system/oauth2/tokens",
        route_name="OAuth2Tokens",
        component="#/views/oauth2/tokens/index.vue",
        icon="lucide:key-round",
        permission_code="system:oauth2-token:list",
        sort=20,
    )
    social = ensure_menu(
        session=session,
        title="menu.socialLogin",
        type="directory",
        parent_id=system.id,
        route_path="/system/social",
        route_name="SocialLogin",
        icon="lucide:rocket",
        sort=86,
    )
    social_clients = ensure_menu(
        session=session,
        title="menu.socialClients",
        type="menu",
        parent_id=social.id,
        route_path="/system/social/clients",
        route_name="SocialClients",
        component="#/views/social/clients/index.vue",
        icon="lucide:settings-2",
        permission_code="system:social-client:list",
        sort=10,
    )
    social_users = ensure_menu(
        session=session,
        title="menu.socialUsers",
        type="menu",
        parent_id=social.id,
        route_path="/system/social/users",
        route_name="SocialUsers",
        component="#/views/social/users/index.vue",
        icon="lucide:users-round",
        permission_code="system:social-user:list",
        sort=20,
    )
    migrate_directory_menu(
        session=session,
        parent=system,
        route_name="Logs",
        legacy_paths=("/logs",),
        target_path="/system/logs",
        sort=90,
    )
    logs = ensure_menu(
        session=session,
        title="menu.logs",
        type="directory",
        parent_id=system.id,
        route_path="/system/logs",
        route_name="Logs",
        icon="lucide:clipboard-list",
        sort=90,
    )
    login_logs = ensure_menu(
        session=session,
        title="menu.loginLogs",
        type="menu",
        parent_id=logs.id,
        route_path="/system/logs/login",
        route_name="LoginLogs",
        component="#/views/logs/login/index.vue",
        icon="lucide:log-in",
        permission_code="system:login-log:list",
        sort=10,
    )
    operation_logs = ensure_menu(
        session=session,
        title="menu.operationLogs",
        type="menu",
        parent_id=logs.id,
        route_path="/system/logs/operation",
        route_name="OperationLogs",
        component="#/views/logs/operation/index.vue",
        icon="lucide:history",
        permission_code="system:operation-log:list",
        sort=20,
    )
    migrate_directory_menu(
        session=session,
        parent=basic_settings,
        route_name="Files",
        legacy_paths=("/files", "/system/files"),
        target_path="/basic-settings/files",
        sort=20,
    )
    files = ensure_menu(
        session=session,
        title="menu.files",
        type="directory",
        parent_id=basic_settings.id,
        route_path="/basic-settings/files",
        route_name="Files",
        icon="lucide:folder",
        sort=20,
    )
    if files.component is not None or files.permission_code is not None:
        files.component = None
        files.permission_code = None
        session.add(files)
        session.flush()
    file_channels = ensure_menu(
        session=session,
        title="menu.fileChannels",
        type="menu",
        parent_id=files.id,
        route_path="/basic-settings/files/channels",
        route_name="FileChannels",
        component="#/views/files/channels/index.vue",
        icon="lucide:database",
        permission_code="system:file:channel:list",
        sort=10,
    )
    file_config = ensure_menu(
        session=session,
        title="menu.fileConfig",
        type="menu",
        parent_id=files.id,
        route_path="/basic-settings/files/config",
        route_name="FileConfig",
        component="#/views/files/config/index.vue",
        icon="lucide:settings-2",
        permission_code="system:file:config:list",
        sort=20,
    )
    file_list = ensure_menu(
        session=session,
        title="menu.fileList",
        type="menu",
        parent_id=files.id,
        route_path="/basic-settings/files/list",
        route_name="FileList",
        component="#/views/files/index.vue",
        icon="lucide:files",
        permission_code="system:file:list",
        sort=30,
    )
    message_center = ensure_menu(
        session=session,
        title="menu.messageCenter",
        type="directory",
        parent_id=system.id,
        route_path="/system/message-center",
        route_name="MessageCenter",
        icon="lucide:messages-square",
        sort=110,
    )
    notices = ensure_menu(
        session=session,
        title="menu.notices",
        type="menu",
        parent_id=message_center.id,
        route_path="/system/message-center/notices",
        route_name="Notices",
        component="#/views/notices/index.vue",
        icon="lucide:megaphone",
        permission_code="system:notice:list",
        sort=10,
    )
    messages = ensure_menu(
        session=session,
        title="menu.messages",
        type="menu",
        parent_id=message_center.id,
        route_path="/system/message-center/messages",
        route_name="Messages",
        component="#/views/messages/index.vue",
        icon="lucide:mail",
        permission_code="personal:message:list",
        sort=20,
    )
    site_messages = ensure_menu(
        session=session,
        title="menu.siteMessages",
        type="directory",
        parent_id=message_center.id,
        route_path="/system/message-center/site-messages",
        route_name="SiteMessages",
        component="#/views/_core/router-view.vue",
        icon="lucide:inbox",
        sort=30,
    )
    site_message_templates = ensure_menu(
        session=session,
        title="menu.siteMessageTemplates",
        type="menu",
        parent_id=site_messages.id,
        route_path="/system/message-center/site-messages/templates",
        route_name="SiteMessageTemplates",
        component="#/views/site-messages/templates/index.vue",
        icon="lucide:archive",
        permission_code="system:site-message-template:list",
        sort=10,
    )
    site_message_list = ensure_menu(
        session=session,
        title="menu.siteMessageList",
        type="menu",
        parent_id=site_messages.id,
        route_path="/system/message-center/site-messages/list",
        route_name="SiteMessageList",
        component="#/views/site-messages/messages/index.vue",
        icon="lucide:edit-3",
        permission_code="system:site-message:list",
        sort=20,
    )
    sms = ensure_menu(
        session=session,
        title="menu.sms",
        type="directory",
        parent_id=message_center.id,
        route_path="/system/message-center/sms",
        route_name="Sms",
        component="#/views/_core/router-view.vue",
        icon="lucide:message-square-more",
        sort=40,
    )
    sms_channels = ensure_menu(
        session=session,
        title="menu.smsChannels",
        type="menu",
        parent_id=sms.id,
        route_path="/system/message-center/sms/channels",
        route_name="SmsChannels",
        component="#/views/sms/channels/index.vue",
        icon="lucide:messages-square",
        permission_code="system:sms-channel:list",
        sort=10,
    )
    sms_templates = ensure_menu(
        session=session,
        title="menu.smsTemplates",
        type="menu",
        parent_id=sms.id,
        route_path="/system/message-center/sms/templates",
        route_name="SmsTemplates",
        component="#/views/sms/templates/index.vue",
        icon="lucide:scroll-text",
        permission_code="system:sms-template:list",
        sort=20,
    )
    sms_logs = ensure_menu(
        session=session,
        title="menu.smsLogs",
        type="menu",
        parent_id=sms.id,
        route_path="/system/message-center/sms/logs",
        route_name="SmsLogs",
        component="#/views/sms/logs/index.vue",
        icon="lucide:send",
        permission_code="system:sms-log:list",
        sort=30,
    )
    mail = ensure_menu(
        session=session,
        title="menu.mail",
        type="directory",
        parent_id=message_center.id,
        route_path="/system/message-center/mail",
        route_name="Mail",
        component="#/views/_core/router-view.vue",
        icon="lucide:mail",
        sort=50,
    )
    mail_accounts = ensure_menu(
        session=session,
        title="menu.mailAccounts",
        type="menu",
        parent_id=mail.id,
        route_path="/system/message-center/mail/accounts",
        route_name="MailAccounts",
        component="#/views/mail/accounts/index.vue",
        icon="lucide:mail-check",
        permission_code="system:mail-account:list",
        sort=10,
    )
    mail_templates = ensure_menu(
        session=session,
        title="menu.mailTemplates",
        type="menu",
        parent_id=mail.id,
        route_path="/system/message-center/mail/templates",
        route_name="MailTemplates",
        component="#/views/mail/templates/index.vue",
        icon="lucide:scroll-text",
        permission_code="system:mail-template:list",
        sort=20,
    )
    mail_logs = ensure_menu(
        session=session,
        title="menu.mailLogs",
        type="menu",
        parent_id=mail.id,
        route_path="/system/message-center/mail/logs",
        route_name="MailLogs",
        component="#/views/mail/logs/index.vue",
        icon="lucide:send",
        permission_code="system:mail-log:list",
        sort=30,
    )
    items = ensure_menu(
        session=session,
        title="menu.items",
        type="menu",
        route_path="/items",
        route_name="Items",
        component="#/views/items/index.vue",
        icon="lucide:list-todo",
        permission_code="business:item:list",
        sort=20,
    )
    button_permissions = [
        (tenants.id, "新增租户", "platform:tenant:create", 6),
        (tenants.id, "编辑租户", "platform:tenant:update", 7),
        (tenants.id, "停用租户", "platform:tenant:delete", 8),
        (tenants.id, "生命周期操作", "platform:tenant:lifecycle", 9),
        (tenants.id, "同步租户菜单", "platform:tenant:sync-menu", 10),
        (tenant_plans.id, "新增套餐", "platform:plan:create", 9),
        (tenant_plans.id, "编辑套餐", "platform:plan:update", 10),
        (tenant_plans.id, "删除套餐", "platform:plan:delete", 11),
        (tenant_plans.id, "套餐菜单授权", "platform:plan:grant-menu", 12),
        (tenant_plans.id, "同步套餐菜单", "platform:plan:sync-menu", 13),
        (tenant_templates.id, "新增模板", "platform:template:create", 12),
        (tenant_templates.id, "编辑模板", "platform:template:update", 13),
        (tenant_templates.id, "删除模板", "platform:template:delete", 14),
        (users.id, "新增用户", "system:user:create", 11),
        (users.id, "编辑用户", "system:user:update", 12),
        (users.id, "删除用户", "system:user:delete", 13),
        (roles.id, "新增角色", "system:role:create", 21),
        (roles.id, "编辑角色", "system:role:update", 22),
        (roles.id, "删除角色", "system:role:delete", 23),
        (menus.id, "新增菜单", "system:menu:create", 31),
        (menus.id, "编辑菜单", "system:menu:update", 32),
        (menus.id, "删除菜单", "system:menu:delete", 33),
        (departments.id, "新增部门", "system:department:create", 41),
        (departments.id, "编辑部门", "system:department:update", 42),
        (departments.id, "删除部门", "system:department:delete", 43),
        (posts.id, "新增岗位", "system:post:create", 51),
        (posts.id, "编辑岗位", "system:post:update", 52),
        (posts.id, "删除岗位", "system:post:delete", 53),
        (dictionaries.id, "新增字典", "system:dict:create", 61),
        (dictionaries.id, "编辑字典", "system:dict:update", 62),
        (dictionaries.id, "删除字典", "system:dict:delete", 63),
        (system_settings.id, "编辑参数", "system:setting:update", 71),
        (oauth2_clients.id, "新增OAuth2客户端", "system:oauth2-client:create", 82),
        (oauth2_clients.id, "编辑OAuth2客户端", "system:oauth2-client:update", 83),
        (oauth2_clients.id, "删除OAuth2客户端", "system:oauth2-client:delete", 84),
        (oauth2_tokens.id, "吊销OAuth2令牌", "system:oauth2-token:delete", 85),
        (social_clients.id, "新增三方客户端", "system:social-client:create", 86),
        (social_clients.id, "编辑三方客户端", "system:social-client:update", 87),
        (social_clients.id, "删除三方客户端", "system:social-client:delete", 88),
        (file_list.id, "上传文件", "system:file:upload", 71),
        (file_list.id, "删除文件", "system:file:delete", 72),
        (file_channels.id, "新增存储渠道", "system:file:channel:create", 73),
        (file_channels.id, "编辑存储渠道", "system:file:channel:update", 74),
        (file_channels.id, "删除存储渠道", "system:file:channel:delete", 75),
        (file_config.id, "编辑上传配置", "system:file:config:update", 76),
        (notices.id, "新增公告", "system:notice:create", 81),
        (notices.id, "编辑公告", "system:notice:update", 82),
        (notices.id, "删除公告", "system:notice:delete", 83),
        (
            site_message_templates.id,
            "新增站内信模板",
            "system:site-message-template:create",
            84,
        ),
        (
            site_message_templates.id,
            "编辑站内信模板",
            "system:site-message-template:update",
            85,
        ),
        (
            site_message_templates.id,
            "删除站内信模板",
            "system:site-message-template:delete",
            86,
        ),
        (
            site_message_templates.id,
            "发送测试站内信",
            "system:site-message-template:send",
            87,
        ),
        (
            site_message_list.id,
            "删除站内信",
            "system:site-message:delete",
            88,
        ),
        (sms_channels.id, "新增短信渠道", "system:sms-channel:create", 91),
        (sms_channels.id, "编辑短信渠道", "system:sms-channel:update", 92),
        (sms_channels.id, "删除短信渠道", "system:sms-channel:delete", 93),
        (sms_templates.id, "新增短信模板", "system:sms-template:create", 94),
        (sms_templates.id, "编辑短信模板", "system:sms-template:update", 95),
        (sms_templates.id, "删除短信模板", "system:sms-template:delete", 96),
        (sms_templates.id, "发送测试短信", "system:sms-template:send", 97),
        (mail_accounts.id, "新增邮箱账号", "system:mail-account:create", 101),
        (mail_accounts.id, "编辑邮箱账号", "system:mail-account:update", 102),
        (mail_accounts.id, "删除邮箱账号", "system:mail-account:delete", 103),
        (mail_templates.id, "新增邮件模板", "system:mail-template:create", 104),
        (mail_templates.id, "编辑邮件模板", "system:mail-template:update", 105),
        (mail_templates.id, "删除邮件模板", "system:mail-template:delete", 106),
        (mail_templates.id, "发送测试邮件", "system:mail-template:send", 107),
        (mail_logs.id, "重发邮件", "system:mail-log:resend", 108),
        (items.id, "新增示例", "business:item:create", 51),
        (items.id, "编辑示例", "business:item:update", 52),
        (items.id, "删除示例", "business:item:delete", 53),
    ]
    buttons = [
        ensure_menu(
            session=session,
            title=title,
            type="button",
            parent_id=parent_id,
            permission_code=permission_code,
            sort=sort,
            is_visible=False,
        )
        for parent_id, title, permission_code, sort in button_permissions
    ]
    return [
        dashboard,
        system,
        tenant_center,
        basic_settings,
        tenants,
        tenant_plans,
        tenant_templates,
        users,
        roles,
        menus,
        departments,
        posts,
        dictionaries,
        system_settings,
        oauth2,
        oauth2_clients,
        oauth2_tokens,
        social,
        social_clients,
        social_users,
        message_center,
        logs,
        login_logs,
        operation_logs,
        files,
        file_channels,
        file_config,
        file_list,
        notices,
        messages,
        site_messages,
        site_message_templates,
        site_message_list,
        sms,
        sms_channels,
        sms_templates,
        sms_logs,
        mail,
        mail_accounts,
        mail_templates,
        mail_logs,
        items,
        *buttons,
    ]


def remove_obsolete_menus(*, session: Session) -> None:
    obsolete_route_paths = {
        "/system/codegen",
        "/system/online-users",
        "/system/operations",
        "/workflows",
    }
    obsolete_permission_prefixes = (
        "system:api-log:",
        "system:codegen:",
        "system:exception-log:",
        "system:scheduled-task:",
        "system:scheduled-task-log:",
        "system:session:",
        "system:translation:",
        "workflow:",
    )
    obsolete_menus = [
        menu
        for menu in session.exec(select(Menu)).all()
        if menu.route_path in obsolete_route_paths
        or (menu.route_path or "").startswith("/system/operations/")
        or (menu.component or "").startswith("#/views/operations/")
        or (menu.component or "").startswith("#/views/system/online-users/")
        or (menu.permission_code or "").startswith(obsolete_permission_prefixes)
    ]
    if not obsolete_menus:
        return

    obsolete_menu_ids = {menu.id for menu in obsolete_menus}
    for role_menu in session.exec(select(RoleMenu)).all():
        if role_menu.menu_id in obsolete_menu_ids:
            session.delete(role_menu)
    session.flush()

    remaining = {menu.id: menu for menu in obsolete_menus}
    while remaining:
        parent_ids = {
            menu.parent_id for menu in remaining.values() if menu.parent_id in remaining
        }
        leaves = [
            menu for menu_id, menu in remaining.items() if menu_id not in parent_ids
        ]
        for menu in leaves:
            session.delete(menu)
            remaining.pop(menu.id)
        session.flush()


def migrate_directory_menu(
    *,
    session: Session,
    parent: Menu,
    route_name: str,
    legacy_paths: tuple[str, ...],
    target_path: str,
    sort: int,
) -> None:
    legacy_menu = session.exec(
        select(Menu).where(
            Menu.route_name == route_name,
            Menu.route_path.in_(legacy_paths),
        )
    ).first()
    if not legacy_menu:
        return

    target_menu = session.exec(
        select(Menu).where(Menu.route_path == target_path)
    ).first()
    if not target_menu:
        legacy_menu.parent_id = parent.id
        legacy_menu.route_path = target_path
        legacy_menu.sort = sort
        legacy_menu.updated_at = get_datetime_utc()
        session.add(legacy_menu)
        session.flush()
        return

    for role_menu in session.exec(
        select(RoleMenu).where(RoleMenu.menu_id == legacy_menu.id)
    ).all():
        target_mapping = session.exec(
            select(RoleMenu).where(
                RoleMenu.role_id == role_menu.role_id,
                RoleMenu.menu_id == target_menu.id,
            )
        ).first()
        if not target_mapping:
            session.add(RoleMenu(role_id=role_menu.role_id, menu_id=target_menu.id))
        session.delete(role_menu)
    session.flush()
    session.delete(legacy_menu)
    session.flush()


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


def ensure_dictionary_type(
    *,
    session: Session,
    tenant: Tenant,
    code: str,
    name: str,
    description: str | None = None,
) -> DictionaryType:
    type_ = session.exec(
        select(DictionaryType).where(
            DictionaryType.tenant_id == tenant.id,
            DictionaryType.code == code,
        )
    ).first()
    if type_:
        return type_

    type_ = DictionaryType(
        tenant_id=tenant.id,
        code=code,
        name=name,
        description=description,
    )
    session.add(type_)
    session.flush()
    return type_


def ensure_dictionary_item(
    *,
    session: Session,
    type_: DictionaryType,
    label: str,
    value: str,
    color: str | None = None,
    sort: int = 0,
) -> DictionaryItem:
    item = session.exec(
        select(DictionaryItem).where(
            DictionaryItem.tenant_id == type_.tenant_id,
            DictionaryItem.type_id == type_.id,
            DictionaryItem.value == value,
        )
    ).first()
    if item:
        return item

    item = DictionaryItem(
        tenant_id=type_.tenant_id,
        type_id=type_.id,
        label=label,
        value=value,
        color=color,
        sort=sort,
    )
    session.add(item)
    session.flush()
    return item


def seed_dictionaries(*, session: Session, tenant: Tenant) -> None:
    user_status = ensure_dictionary_type(
        session=session,
        tenant=tenant,
        code="user_status",
        name="用户状态",
        description="用户启用状态",
    )
    ensure_dictionary_item(
        session=session, type_=user_status, label="启用", value="active", color="green"
    )
    ensure_dictionary_item(
        session=session, type_=user_status, label="禁用", value="inactive", color="red"
    )

    yes_no = ensure_dictionary_type(
        session=session,
        tenant=tenant,
        code="yes_no",
        name="是否",
        description="通用是否选项",
    )
    ensure_dictionary_item(session=session, type_=yes_no, label="是", value="yes")
    ensure_dictionary_item(
        session=session, type_=yes_no, label="否", value="no", sort=1
    )

    business_status = ensure_dictionary_type(
        session=session,
        tenant=tenant,
        code="business_status",
        name="业务状态",
        description="示例业务状态",
    )
    ensure_dictionary_item(
        session=session,
        type_=business_status,
        label="草稿",
        value="draft",
        color="default",
    )
    ensure_dictionary_item(
        session=session,
        type_=business_status,
        label="已发布",
        value="published",
        color="green",
        sort=1,
    )
    user_type = ensure_dictionary_type(
        session=session,
        tenant=tenant,
        code="user_type",
        name="用户类型",
        description="登录主体类型",
    )
    ensure_dictionary_item(
        session=session, type_=user_type, label="管理后台", value="admin"
    )
    ensure_dictionary_item(
        session=session, type_=user_type, label="移动端", value="member", sort=1
    )

    oauth2_grant_type = ensure_dictionary_type(
        session=session,
        tenant=tenant,
        code="system_oauth2_grant_type",
        name="OAuth 2.0 授权类型",
        description="OAuth 2.0 客户端授权模式",
    )
    for sort, value in enumerate(
        [
            "authorization_code",
            "refresh_token",
            "password",
            "client_credentials",
            "implicit",
        ]
    ):
        ensure_dictionary_item(
            session=session,
            type_=oauth2_grant_type,
            label=value,
            value=value,
            sort=sort,
        )

    social_type = ensure_dictionary_type(
        session=session,
        tenant=tenant,
        code="system_social_type",
        name="社交类型",
        description="第三方登录平台类型",
    )
    social_options = [
        ("gitee", "Gitee"),
        ("dingtalk", "钉钉"),
        ("wechat_open", "微信开放平台"),
        ("wechat_mp", "微信公众平台"),
        ("wechat_mini", "微信小程序"),
        ("wechat_work", "企业微信"),
    ]
    for sort, (value, label) in enumerate(social_options):
        ensure_dictionary_item(
            session=session,
            type_=social_type,
            label=label,
            value=value,
            sort=sort,
        )


def ensure_setting(
    *,
    session: Session,
    tenant: Tenant,
    key: str,
    name: str,
    value: str,
    value_type: str,
    group: str,
    description: str | None = None,
    is_public: bool = False,
    is_system: bool = False,
) -> SystemSetting:
    setting = session.exec(
        select(SystemSetting).where(
            SystemSetting.tenant_id == tenant.id,
            SystemSetting.key == key,
        )
    ).first()
    if setting:
        return setting

    setting = SystemSetting(
        tenant_id=tenant.id,
        key=key,
        name=name,
        value=value,
        value_type=value_type,
        group=group,
        description=description,
        is_public=is_public,
        is_system=is_system,
    )
    session.add(setting)
    session.flush()
    return setting


def seed_settings(*, session: Session, tenant: Tenant) -> None:
    ensure_setting(
        session=session,
        tenant=tenant,
        key="system.name",
        name="系统名称",
        value="Fast Vben Admin",
        value_type="string",
        group="system",
        description="显示在后台中的系统名称",
        is_public=True,
        is_system=True,
    )
    ensure_setting(
        session=session,
        tenant=tenant,
        key="system.default_page_size",
        name="默认分页大小",
        value="20",
        value_type="number",
        group="system",
        is_public=True,
        is_system=True,
    )
    ensure_setting(
        session=session,
        tenant=tenant,
        key="auth.allow_register",
        name="是否开放注册",
        value="false",
        value_type="boolean",
        group="auth",
        description="MVP 默认关闭公开注册",
        is_public=True,
        is_system=True,
    )
    ensure_setting(
        session=session,
        tenant=tenant,
        key="upload.max_size_mb",
        name="上传大小限制 MB",
        value="10",
        value_type="number",
        group="upload",
        is_public=False,
        is_system=True,
    )
    ensure_setting(
        session=session,
        tenant=tenant,
        key="upload.allowed_extensions",
        name="允许上传扩展名",
        value=settings.UPLOAD_ALLOWED_EXTENSIONS,
        value_type="string",
        group="upload",
        is_public=False,
        is_system=True,
    )
    ensure_setting(
        session=session,
        tenant=tenant,
        key="upload.default_public",
        name="默认公开访问",
        value="false",
        value_type="boolean",
        group="upload",
        is_public=False,
        is_system=True,
    )
    ensure_setting(
        session=session,
        tenant=tenant,
        key="upload.presigned_url_expire_seconds",
        name="下载链接有效期秒数",
        value=str(settings.S3_PRESIGNED_URL_EXPIRE_SECONDS),
        value_type="number",
        group="upload",
        is_public=False,
        is_system=True,
    )


def seed_storage_channels(*, session: Session, tenant: Tenant) -> None:
    existing_default = session.exec(
        select(FileStorageChannel).where(
            FileStorageChannel.tenant_id == tenant.id,
            FileStorageChannel.is_default,
        )
    ).first()
    if existing_default:
        return

    provider = settings.STORAGE_PROVIDER
    channel = FileStorageChannel(
        tenant_id=tenant.id,
        name="本地存储" if provider == "local" else "默认对象存储",
        code="local" if provider == "local" else "default-s3",
        provider=provider,
        endpoint_url=settings.S3_ENDPOINT_URL,
        region=settings.S3_REGION,
        bucket=settings.S3_BUCKET,
        access_key_id=settings.S3_ACCESS_KEY_ID,
        secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        object_prefix=settings.S3_OBJECT_PREFIX,
        addressing_style=settings.S3_ADDRESSING_STYLE,
        auto_create_bucket=settings.S3_AUTO_CREATE_BUCKET,
        is_default=True,
        is_active=True,
        remark="由环境变量初始化，可在后台调整。",
    )
    session.add(channel)
    session.flush()


def seed_sms_channels(*, session: Session, tenant: Tenant) -> None:
    debug_channel = session.exec(
        select(SmsChannel).where(
            SmsChannel.tenant_id == tenant.id,
            SmsChannel.code == "debug",
        )
    ).first()
    if not debug_channel:
        debug_channel = SmsChannel(
            tenant_id=tenant.id,
            name="本地调试渠道",
            code="debug",
            provider="debug",
            signature="系统通知",
            is_default=True,
            is_active=True,
            remark="仅记录发送结果，不会向真实手机号发送短信。",
        )
        session.add(debug_channel)
        session.flush()

    sample_template = session.exec(
        select(SmsTemplate).where(
            SmsTemplate.tenant_id == tenant.id,
            SmsTemplate.code == "verify_code",
        )
    ).first()
    if not sample_template:
        session.add(
            SmsTemplate(
                tenant_id=tenant.id,
                type="verification",
                code="verify_code",
                name="验证码",
                content="您的验证码为 {code}，5 分钟内有效。",
                params="code",
                remark="系统内置演示模板，可用于验证短信渠道和日志。",
                channel_id=debug_channel.id,
                channel_code=debug_channel.code,
                is_active=True,
            )
        )
        session.flush()


def seed_mail_accounts(*, session: Session, tenant: Tenant) -> None:
    if not settings.SMTP_HOST or not settings.EMAILS_FROM_EMAIL:
        return

    default_account = session.exec(
        select(MailAccount).where(
            MailAccount.tenant_id == tenant.id,
            MailAccount.code == "default",
        )
    ).first()
    if not default_account:
        default_account = MailAccount(
            tenant_id=tenant.id,
            name="系统邮箱账号",
            code="default",
            email=settings.EMAILS_FROM_EMAIL,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            host=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            ssl_enable=settings.SMTP_SSL,
            starttls_enable=settings.SMTP_TLS,
            is_default=True,
            is_active=True,
            remark="由环境变量初始化，可在后台调整。",
        )
        session.add(default_account)
        session.flush()

    sample_template = session.exec(
        select(MailTemplate).where(
            MailTemplate.tenant_id == tenant.id,
            MailTemplate.code == "welcome_mail",
        )
    ).first()
    if not sample_template:
        session.add(
            MailTemplate(
                tenant_id=tenant.id,
                code="welcome_mail",
                name="欢迎邮件",
                account_id=default_account.id,
                account_code=default_account.code,
                nickname=settings.EMAILS_FROM_NAME,
                title="欢迎加入 {project}",
                content="<p>您好，{name}。</p><p>欢迎使用 {project}。</p>",
                params="project,name",
                remark="系统内置演示模板，可用于验证邮箱账号和日志。",
                is_active=True,
            )
        )
        session.flush()


def seed_site_message_templates(*, session: Session, tenant: Tenant) -> None:
    welcome_template = session.exec(
        select(SiteMessageTemplate).where(
            SiteMessageTemplate.tenant_id == tenant.id,
            SiteMessageTemplate.code == "system_notice",
        )
    ).first()
    if not welcome_template:
        session.add(
            SiteMessageTemplate(
                tenant_id=tenant.id,
                code="system_notice",
                name="通知公告",
                sender_name="通知公告",
                content="尊敬的用户，{title}",
                type="notice",
                params="title",
                remark="系统内置演示模板，可用于验证站内信发送和列表。",
                is_active=True,
            )
        )
        session.flush()


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


def replace_role_menus(*, session: Session, role: Role, menus: list[Menu]) -> None:
    session.exec(delete(RoleMenu).where(RoleMenu.role_id == role.id))
    for menu in menus:
        session.add(RoleMenu(role_id=role.id, menu_id=menu.id))


def sync_tenant_plan_role_menus(*, session: Session, tenant: Tenant) -> bool:
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
