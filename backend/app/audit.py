import time
from collections.abc import Awaitable, Callable
from uuid import UUID

import jwt
from fastapi import Request, Response
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session

from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.core.tenancy import DEFAULT_TENANT_ID
from app.models import LoginLog, OperationLog, TokenPayload, User

SENSITIVE_PATH_PARTS = (
    "/login/access-token",
    "/login/enterprise-oidc/exchange",
    "/password-recovery",
    "/reset-password",
)


def get_client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else None


def get_user_agent(request: Request) -> str | None:
    user_agent = request.headers.get("user-agent")
    return user_agent[:500] if user_agent else None


def create_login_log(
    *,
    session: Session,
    request: Request,
    email: str,
    status: str,
    user: User | None = None,
    tenant_id: UUID = DEFAULT_TENANT_ID,
    failure_reason: str | None = None,
) -> None:
    session.add(
        LoginLog(
            tenant_id=tenant_id,
            user_id=user.id if user else None,
            email=email,
            ip=get_client_ip(request),
            user_agent=get_user_agent(request),
            status=status,
            failure_reason=failure_reason,
        )
    )
    session.commit()


def should_log_operation(request: Request) -> bool:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return False
    path = request.url.path
    if not path.startswith(settings.API_V1_STR):
        return False
    if f"{settings.API_V1_STR}/logs/" in path:
        return False
    if any(part in path for part in SENSITIVE_PATH_PARTS):
        return False
    return True


def parse_token_user(
    session: Session, request: Request
) -> tuple[str | None, UUID | None, UUID]:
    authorization = request.headers.get("authorization")
    if not authorization or not authorization.lower().startswith("bearer "):
        return None, None, DEFAULT_TENANT_ID

    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[security.ALGORITHM],
        )
        token_data = TokenPayload(**payload)
    except InvalidTokenError, ValidationError:
        return None, None, DEFAULT_TENANT_ID

    if not token_data.sub:
        return None, None, DEFAULT_TENANT_ID

    user = session.get(User, token_data.sub)
    if not user:
        return None, None, DEFAULT_TENANT_ID
    return user.email, user.id, token_data.tenant_id or DEFAULT_TENANT_ID


def get_operation_module(path: str) -> str:
    relative_path = path.removeprefix(settings.API_V1_STR).strip("/")
    return relative_path.split("/", 1)[0] or "api"


def get_operation_action(method: str) -> str:
    return {
        "DELETE": "delete",
        "PATCH": "update",
        "POST": "create",
        "PUT": "update",
    }.get(method.upper(), method.lower())


async def audit_operation_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    if not should_log_operation(request):
        return await call_next(request)

    started_at = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        with Session(engine) as session:
            email, user_id, tenant_id = parse_token_user(
                session=session,
                request=request,
            )
            session.add(
                OperationLog(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    email=email,
                    module=get_operation_module(request.url.path),
                    action=get_operation_action(request.method),
                    method=request.method,
                    path=request.url.path,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    ip=get_client_ip(request),
                    user_agent=get_user_agent(request),
                    request_summary=None,
                    response_summary=None,
                )
            )
            session.commit()
