from fastapi import APIRouter, Depends
from pydantic.networks import EmailStr
from sqlmodel import select

from app.api.deps import SessionDep, get_current_active_superuser
from app.core.cache import redis_cache
from app.models import HealthDependencyStatus, HealthStatus, Message
from app.utils import generate_test_email, send_email

router = APIRouter(prefix="/utils", tags=["utils"])


@router.post(
    "/test-email/",
    dependencies=[Depends(get_current_active_superuser)],
    status_code=201,
)
def test_email(email_to: EmailStr) -> Message:
    """
    Test emails.
    """
    email_data = generate_test_email(email_to=email_to)
    send_email(
        email_to=email_to,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
    return Message(message="Test email sent")


@router.get("/health-check")
async def health_check() -> bool:
    return True


@router.get("/health-status", response_model=HealthStatus)
def health_status(session: SessionDep) -> HealthStatus:
    database_ok = False
    try:
        session.exec(select(1)).one()
        database_ok = True
    except Exception:
        database_ok = False

    redis_status = redis_cache.health_status()
    degraded = bool(redis_status["degraded"])
    return HealthStatus(
        ok=database_ok,
        degraded=degraded,
        database=HealthDependencyStatus(
            status="up" if database_ok else "down",
            available=database_ok,
        ),
        redis=HealthDependencyStatus(
            status=str(redis_status["status"]),
            enabled=bool(redis_status["enabled"]),
            degraded=bool(redis_status["degraded"]),
            available=bool(redis_status["available"]),
        ),
    )
