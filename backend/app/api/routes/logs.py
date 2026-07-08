from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import col, func, or_, select

from app.api.deps import SessionDep, require_permission
from app.models import (
    LoginLog,
    LoginLogPublic,
    LoginLogsPublic,
    OperationLog,
    OperationLogPublic,
    OperationLogsPublic,
)

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get(
    "/login",
    dependencies=[Depends(require_permission("system:login-log:list"))],
    response_model=LoginLogsPublic,
)
def read_login_logs(
    session: SessionDep,
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    status: str | None = None,
) -> Any:
    filters = []
    if status:
        filters.append(LoginLog.status == status)
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            or_(
                col(LoginLog.email).ilike(pattern),
                col(LoginLog.ip).ilike(pattern),
                col(LoginLog.failure_reason).ilike(pattern),
            )
        )

    count_statement = select(func.count()).select_from(LoginLog)
    if filters:
        count_statement = count_statement.where(*filters)
    count = session.exec(count_statement).one()

    statement = select(LoginLog)
    if filters:
        statement = statement.where(*filters)
    statement = (
        statement.order_by(col(LoginLog.created_at).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    logs = session.exec(statement).all()
    return LoginLogsPublic(
        items=[LoginLogPublic.model_validate(log) for log in logs],
        total=count,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/operation",
    dependencies=[Depends(require_permission("system:operation-log:list"))],
    response_model=OperationLogsPublic,
)
def read_operation_logs(
    session: SessionDep,
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    method: str | None = None,
    status_code: int | None = None,
) -> Any:
    filters = []
    if method:
        filters.append(OperationLog.method == method.upper())
    if status_code:
        filters.append(OperationLog.status_code == status_code)
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            or_(
                col(OperationLog.email).ilike(pattern),
                col(OperationLog.module).ilike(pattern),
                col(OperationLog.path).ilike(pattern),
                col(OperationLog.ip).ilike(pattern),
            )
        )

    count_statement = select(func.count()).select_from(OperationLog)
    if filters:
        count_statement = count_statement.where(*filters)
    count = session.exec(count_statement).one()

    statement = select(OperationLog)
    if filters:
        statement = statement.where(*filters)
    statement = (
        statement.order_by(col(OperationLog.created_at).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    logs = session.exec(statement).all()
    return OperationLogsPublic(
        items=[OperationLogPublic.model_validate(log) for log in logs],
        total=count,
        page=page,
        page_size=page_size,
    )
