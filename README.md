# Fast Vben Admin

**中文** | [English](./README.en-US.md)

Fast Vben Admin 是一个全栈后台管理模板，后端基于 FastAPI，前端基于 Vue Vben Admin 的 `web-antd` 应用，适合作为中后台系统、RBAC 权限系统和业务管理平台的二次开发基础。

## 项目状态

当前项目已经具备可扩展的 FastAPI + Vue Vben Admin 基础能力，并接入了真实后端 API 与 `web-antd` 前端。

已实现模块：

- 登录认证、当前用户、密码找回、个人资料和密码修改。
- 用户、角色、菜单、部门、字典和系统设置管理。
- RBAC 权限码、后端权限校验和后端动态菜单。
- 登录日志和操作日志。
- 文件上传、下载、删除、头像上传和文件管理页面。
- 通知发布和个人消息。
- 用户导出、事项导出、事项 CSV 模板和 CSV 导入。
- OpenAPI TypeScript 客户端生成。
- 后端、前端和 Docker Compose CI 工作流。

本地已验证：

- 后端 lint：`uv run ruff check app tests`
- 后端测试：`POSTGRES_SERVER=localhost SMTP_HOST='' uv run pytest`
- 前端类型检查：`pnpm -F @vben/web-antd run typecheck`
- 前端构建：`pnpm -F @vben/web-antd run build`
- OpenAPI 生成：`pnpm generate:api`

Docker Compose 工作流已配置在 `.github/workflows/docker-compose.yml`。本地 Docker 验证需要提前安装 Docker。

## 技术栈

- 后端：FastAPI、SQLModel、Alembic、PostgreSQL、JWT、Pytest、uv
- 前端：Vue 3、Vite、TypeScript、Pinia、Vue Router、Vue Vben Admin、Ant Design Vue、pnpm
- 基础设施：Docker Compose、Nginx、Mailcatcher/Mailpit、Adminer

## Preview

### 仪表盘

![仪表盘预览](./docs/assets/preview-dashboard.png)

### 用户管理

![用户管理预览](./docs/assets/preview-users.png)

### 字典管理

![字典管理预览](./docs/assets/preview-dictionaries.png)

## 快速开始

```bash
cp .env.example .env
docker compose up --build
```

Windows 环境可以使用初始化脚本创建 `.env` 并安装前后端依赖：

```powershell
pnpm setup
```

默认本地地址：

- 前端：http://localhost:5173
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs
- OpenAPI Schema：http://localhost:8000/api/v1/openapi.json
- 邮件预览：http://localhost:1080
- 数据库管理：http://localhost:8080

默认本地管理员：

- 邮箱：`admin@example.com`
- 密码：`changethis`

任何非本地环境部署前，请务必修改所有默认密钥和密码。

## 本地开发

后端：

```bash
cd backend
uv sync
uv run alembic upgrade head
fastapi dev app/main.py
```

如果直接连接本机 PostgreSQL，而不是 Docker Compose 内的数据库，需要覆盖 Docker 专用主机名：

```powershell
$env:POSTGRES_SERVER='localhost'
```

前端：

```bash
cd frontend
pnpm install
pnpm dev
```

常用根目录命令：

```bash
pnpm backend:lint
pnpm backend:test
pnpm frontend:typecheck
pnpm frontend:build
pnpm frontend:e2e
pnpm generate:api
```

`pnpm generate:api` 默认读取 `http://localhost:8000/api/v1/openapi.json`，并将生成的 TypeScript 文件写入 `frontend/apps/web-antd/src/api/generated`。如需指定其他 OpenAPI 地址，可通过 `OPENAPI_INPUT` 覆盖。

## 更多文档

- `docs/development.md`
- `docs/deployment.md`
- `docs/api-contract.md`
- `docs/rbac.md`
- `docs/module-guide.md`
- `docs/faq.md`

## 参考项目

本项目整合并参考了以下项目的思路和代码：

- Full Stack FastAPI Template
- Vue Vben Admin
