import sentry_sdk
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware

from app.api.main import api_router
from app.audit import audit_operation_middleware
from app.core.config import settings


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


ERROR_CODE_BY_STATUS = {
    400: "BAD_REQUEST",
    401: "AUTH_TOKEN_INVALID",
    403: "USER_FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    500: "INTERNAL_SERVER_ERROR",
}

ERROR_CODE_BY_MESSAGE = {
    "Incorrect email or password": "AUTH_INVALID_CREDENTIALS",
    "Inactive user": "USER_INACTIVE",
    "Could not validate credentials": "AUTH_TOKEN_INVALID",
    "User not found": "USER_NOT_FOUND",
    "Not enough permissions": "ITEM_FORBIDDEN",
    "The user doesn't have enough privileges": "USER_FORBIDDEN",
}


def error_response(
    *, status_code: int, code: str, message: str, details: dict | list | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
            "details": details or {},
        },
    )


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
)

app.middleware("http")(audit_operation_middleware)


@app.exception_handler(HTTPException)
async def http_exception_handler(
    _request: Request, exc: HTTPException
) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return error_response(
        status_code=exc.status_code,
        code=ERROR_CODE_BY_MESSAGE.get(
            detail, ERROR_CODE_BY_STATUS.get(exc.status_code, "REQUEST_ERROR")
        ),
        message=detail,
        details={} if isinstance(exc.detail, str) else {"detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    return error_response(
        status_code=422,
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details={"errors": exc.errors()},
    )


# Set all CORS enabled origins
if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)
