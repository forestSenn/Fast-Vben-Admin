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
uv run python -m app.modules.migrate --edition suite
uv run python -m app.initial_data
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

端到端测试需要先启动后端，并让前端指向同一个 API。若本机 `8000` 已被占用，可把后端启动在其他端口：

```powershell
cd backend
$env:POSTGRES_SERVER='localhost'
$env:POSTGRES_PORT='5432'
$env:POSTGRES_DB='app'
$env:POSTGRES_USER='postgres'
$env:POSTGRES_PASSWORD='changethis'
$env:BACKEND_CORS_ORIGINS='http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174'
$env:FRONTEND_HOST='http://127.0.0.1:5174'
uv run uvicorn app.main:app --host 127.0.0.1 --port 8002

cd ..
$env:VITE_GLOB_API_URL='http://127.0.0.1:8002/api/v1'
$env:E2E_API_URL='http://127.0.0.1:8002/api/v1'
$env:E2E_BASE_URL='http://127.0.0.1:5174'
pnpm frontend:e2e
```

## API 类型生成

推荐从仓库根目录执行：

```powershell
pnpm generate:api
```

该命令会从当前 edition 导出临时 OpenAPI schema，分别生成平台和已启用业务模块客户端，不依赖 `localhost:8000` 上已有服务。

指定产品组合：

```powershell
pnpm generate:api -- --edition base
pnpm generate:api -- --edition suite
```

也可以指定外部 OpenAPI 地址或本地 OpenAPI 文件：

```powershell
$env:OPENAPI_INPUT='../openapi.local.json'
pnpm --dir frontend generate:api
```

## 产品发行版

后端通过 `APP_EDITION` 选择产品组合。当前可用发行版为：

- `base`：仅平台基座。
- `items`：平台基座和 Items 模块。
- `suite`：当前默认发行版，包含所有已交付模块，即平台基座、Items 和 ERP。

开发环境默认使用 `suite`。生成可随镜像发布的 Manifest：

```powershell
pnpm generate:manifest -- --edition suite --output build/build-manifest.json
```

部署时可设置 `BUILD_MANIFEST_PATH` 指向该文件。应用会校验其 digest、edition 和当前代码中的模块定义；不一致时启动失败。启动还会拒绝数据库中仍标记为 enabled 但未打包的模块，以及 enabled 但尚未 ready 的模块。前端可通过 `/api/v1/platform/modules/manifest` 获取不含敏感信息的 edition、模块版本和 digest。

模块迁移必须从 edition 编排器执行。它会取得 PostgreSQL advisory lock，并审计 `bundled`、`migrating`、`ready` 和 `degraded` 的状态转换；失败时只降级失败模块：

```powershell
pnpm migrate:edition -- --edition suite
```

跨模块状态变更通过事务 Outbox 投递。开发环境可单次处理积压事件：

```powershell
pnpm outbox:dispatch
```

## 新增模块顺序

1. 在 `backend/app/modules` 增加 `ModuleDefinition`，声明模块编码、版本、依赖、路由和权限命名空间，并在模块注册表中注册。
2. 在 `editions/<edition>.yaml` 中选择该模块；不要直接修改 `api/main.py` 的总路由列表。
3. 在模块拥有的模型和迁移位置增加数据结构，并在 `ModuleDefinition` 中声明迁移命名空间；编排器负责按 Manifest 和依赖顺序执行。
4. 在模块提供的初始化逻辑中增加菜单和权限码。
5. 使用事务 Outbox 发布跨模块事件；对外部能力调用时持久化 provider binding，不能在进行中实例上自动替换提供者。
6. 运行 Manifest、迁移、测试和 edition API 类型生成。
7. 在 `frontend/apps/web-antd/src/modules/<module>` 增加 API 封装和页面。
