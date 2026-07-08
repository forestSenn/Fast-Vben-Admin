# 本地开发

## 环境

- Python 3.14
- Node.js 22.18+
- pnpm 11.7+
- PostgreSQL 17+ 或 Docker Compose

## 后端

本机 PostgreSQL 运行时，覆盖 Docker 内部主机名：

```powershell
$env:POSTGRES_SERVER='localhost'
$env:POSTGRES_PORT='5432'
$env:POSTGRES_DB='app'
$env:POSTGRES_USER='postgres'
$env:POSTGRES_PASSWORD='changethis'
cd backend
uv run alembic upgrade head
uv run fastapi dev app/main.py
```

常用检查：

```powershell
uv run ruff check app tests
uv run pytest
```

## 前端

```powershell
cd frontend
pnpm install
pnpm -F @vben/web-antd run dev
pnpm -F @vben/web-antd run typecheck
pnpm -F @vben/web-antd run build
```

## API 类型生成

后端启动在 `http://localhost:8000` 后执行：

```powershell
pnpm generate:api
```

也可以用本地 OpenAPI 文件：

```powershell
$env:OPENAPI_INPUT='../openapi.local.json'
pnpm --dir frontend generate:api
```

## 新增模块顺序

1. 在 `backend/app/models.py` 增加模型和 Pydantic schema。
2. 在 `backend/app/alembic/versions` 增加迁移。
3. 在 `backend/app/api/routes` 增加路由，并在 `api/main.py` 注册。
4. 在 `backend/app/core/db.py` 增加菜单和权限码。
5. 运行迁移、测试和 API 类型生成。
6. 在 `frontend/apps/web-antd/src/api/core` 增加 API 封装。
7. 在 `frontend/apps/web-antd/src/views` 增加页面。
