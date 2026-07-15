from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import extract, func
from sqlmodel import Session, col, select

from app.api.deps import SessionDep, require_permission
from app.models import (
    DashboardAnalytics,
    DashboardHourlyTrend,
    DashboardMonthlyVisit,
    DashboardNamedValue,
    DashboardOverview,
    DashboardRadarSeries,
    FileAsset,
    LoginLog,
    OperationLog,
    User,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

DEVICE_CATEGORIES = ("网页", "移动端", "Ipad", "客户端", "第三方", "其它")
METHOD_LABELS = {
    "GET": "查询请求",
    "POST": "创建操作",
    "PUT": "更新操作",
    "PATCH": "修改操作",
    "DELETE": "删除操作",
}
MODULE_LABELS = {
    "users": "用户",
    "items": "资源",
    "files": "文件",
    "roles": "角色",
    "menus": "菜单",
    "departments": "部门",
    "dictionaries": "字典",
    "notices": "公告",
    "settings": "设置",
    "logs": "日志",
    "login": "登录",
    "permissions": "权限",
}


def start_of_day(moment: datetime) -> datetime:
    return moment.replace(hour=0, minute=0, second=0, microsecond=0)


def start_of_month(moment: datetime) -> datetime:
    return moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def classify_user_agent(user_agent: str | None) -> str:
    if not user_agent:
        return "其它"
    ua = user_agent.lower()
    if "ipad" in ua:
        return "Ipad"
    if "mobile" in ua or "android" in ua or "iphone" in ua:
        return "移动端"
    if "electron" in ua:
        return "客户端"
    if any(token in ua for token in ("postman", "curl", "python-requests", "httpie")):
        return "第三方"
    if any(token in ua for token in ("windows", "macintosh", "linux")):
        return "网页"
    return "其它"


def count_since(
    session: Session, model: type, column_name: str, since: datetime
) -> int:
    created_at = getattr(model, column_name)
    statement = select(func.count()).select_from(model).where(col(created_at) >= since)
    return session.exec(statement).one()


def count_total(session: Session, model: type) -> int:
    return session.exec(select(func.count()).select_from(model)).one()


def count_login_since(
    session: Session, since: datetime, *, success_only: bool = False
) -> int:
    statement = (
        select(func.count())
        .select_from(LoginLog)
        .where(col(LoginLog.created_at) >= since)
    )
    if success_only:
        statement = statement.where(LoginLog.status == "success")
    return session.exec(statement).one()


def count_login_total(session: Session, *, success_only: bool = False) -> int:
    statement = select(func.count()).select_from(LoginLog)
    if success_only:
        statement = statement.where(LoginLog.status == "success")
    return session.exec(statement).one()


def get_hourly_trends(
    session: Session, day_start: datetime
) -> list[DashboardHourlyTrend]:
    day_end = day_start + timedelta(days=1)
    login_rows = session.exec(
        select(
            extract("hour", LoginLog.created_at).label("hour"),
            func.count().label("count"),
        )
        .where(col(LoginLog.created_at) >= day_start)
        .where(col(LoginLog.created_at) < day_end)
        .group_by(extract("hour", LoginLog.created_at))
    ).all()
    operation_rows = session.exec(
        select(
            extract("hour", OperationLog.created_at).label("hour"),
            func.count().label("count"),
        )
        .where(col(OperationLog.created_at) >= day_start)
        .where(col(OperationLog.created_at) < day_end)
        .group_by(extract("hour", OperationLog.created_at))
    ).all()

    login_by_hour = {int(row.hour): int(row.count) for row in login_rows}
    operation_by_hour = {int(row.hour): int(row.count) for row in operation_rows}

    return [
        DashboardHourlyTrend(
            hour=f"{hour}:00",
            login_count=login_by_hour.get(hour, 0),
            operation_count=operation_by_hour.get(hour, 0),
        )
        for hour in range(6, 24)
    ]


def get_monthly_visits(session: Session, year: int) -> list[DashboardMonthlyVisit]:
    year_start = datetime(year, 1, 1, tzinfo=UTC)
    year_end = datetime(year + 1, 1, 1, tzinfo=UTC)
    rows = session.exec(
        select(
            extract("month", LoginLog.created_at).label("month"),
            func.count().label("count"),
        )
        .where(col(LoginLog.created_at) >= year_start)
        .where(col(LoginLog.created_at) < year_end)
        .where(LoginLog.status == "success")
        .group_by(extract("month", LoginLog.created_at))
        .order_by(extract("month", LoginLog.created_at))
    ).all()
    counts = {int(row.month): int(row.count) for row in rows}
    return [
        DashboardMonthlyVisit(month=f"{month}月", count=counts.get(month, 0))
        for month in range(1, 13)
    ]


def get_device_counts(
    session: Session, model: type, since: datetime | None = None
) -> dict[str, int]:
    statement = select(model.user_agent)
    created_at = getattr(model, "created_at", None)
    if since is not None and created_at is not None:
        statement = statement.where(col(created_at) >= since)
    rows = session.exec(statement).all()
    counts = dict.fromkeys(DEVICE_CATEGORIES, 0)
    for user_agent in rows:
        category = classify_user_agent(user_agent)
        counts[category] += 1
    return counts


def get_login_sources(session: Session) -> list[DashboardNamedValue]:
    rows = session.exec(
        select(LoginLog.status, func.count())
        .group_by(LoginLog.status)
        .order_by(func.count().desc())
    ).all()
    labels = {"success": "登录成功", "fail": "登录失败"}
    return [
        DashboardNamedValue(name=labels.get(status, status), value=int(count))
        for status, count in rows
        if count
    ]


def get_module_distribution(session: Session) -> list[DashboardNamedValue]:
    rows = session.exec(
        select(OperationLog.module, func.count())
        .group_by(OperationLog.module)
        .order_by(func.count().desc())
        .limit(8)
    ).all()
    return [
        DashboardNamedValue(
            name=MODULE_LABELS.get(module, module),
            value=int(count),
        )
        for module, count in rows
        if count
    ]


def get_method_distribution(session: Session) -> list[DashboardNamedValue]:
    rows = session.exec(
        select(OperationLog.method, func.count())
        .group_by(OperationLog.method)
        .order_by(func.count().desc())
    ).all()
    return [
        DashboardNamedValue(
            name=METHOD_LABELS.get(method.upper(), method.upper()),
            value=int(count),
        )
        for method, count in rows
        if count
    ]


@router.get(
    "/analytics",
    dependencies=[Depends(require_permission("dashboard:view"))],
    response_model=DashboardAnalytics,
)
def read_dashboard_analytics(session: SessionDep) -> Any:
    now = datetime.now(UTC)
    today_start = start_of_day(now)
    month_start = start_of_month(now)

    overview = DashboardOverview(
        user_count=count_since(session, User, "created_at", month_start),
        user_total=count_total(session, User),
        login_count=count_login_since(session, today_start, success_only=True),
        login_total=count_login_total(session, success_only=True),
        file_count=count_since(session, FileAsset, "created_at", month_start),
        file_total=count_total(session, FileAsset),
        operation_count=count_since(session, OperationLog, "created_at", today_start),
        operation_total=count_total(session, OperationLog),
    )

    login_device_counts = get_device_counts(session, LoginLog)
    operation_device_counts = get_device_counts(session, OperationLog, month_start)
    device_radar = [
        DashboardRadarSeries(
            name="访问",
            values=[login_device_counts[category] for category in DEVICE_CATEGORIES],
        ),
        DashboardRadarSeries(
            name="趋势",
            values=[
                operation_device_counts[category] for category in DEVICE_CATEGORIES
            ],
        ),
    ]

    login_sources = get_login_sources(session)
    if not login_sources:
        login_sources = [DashboardNamedValue(name="暂无数据", value=0)]

    module_distribution = get_module_distribution(session)
    if not module_distribution:
        method_distribution = get_method_distribution(session)
        module_distribution = method_distribution or [
            DashboardNamedValue(name="暂无数据", value=0)
        ]

    return DashboardAnalytics(
        overview=overview,
        hourly_trends=get_hourly_trends(session, today_start),
        monthly_visits=get_monthly_visits(session, now.year),
        device_radar=device_radar,
        login_sources=login_sources,
        module_distribution=module_distribution,
    )
