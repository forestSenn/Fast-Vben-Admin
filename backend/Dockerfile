FROM python:3.14

ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PATH="/app/backend/.venv/bin:$PATH"
ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV UV_INDEX_URL=https://pypi.org/simple

RUN pip install --no-cache-dir uv==0.9.26

WORKDIR /app/backend

COPY ./backend/pyproject.toml ./backend/uv.lock ./backend/alembic.ini ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY ./backend/scripts ./scripts
COPY ./backend/app ./app

CMD ["fastapi", "run", "app/main.py", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
