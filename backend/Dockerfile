FROM python:3.14

ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PATH="/app/backend/.venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

WORKDIR /app/backend

COPY ./backend/pyproject.toml ./backend/alembic.ini ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

COPY ./backend/scripts ./scripts
COPY ./backend/app ./app

CMD ["fastapi", "run", "app/main.py", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
