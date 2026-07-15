# Fast Vben Admin

**中文** | [English](./README.en-US.md)

Fast Vben Admin 是一个全栈后台管理模板，后端基于 FastAPI，前端基于 Vue Vben Admin 的 `web-antd` 应用，适合作为中后台系统、RBAC 权限系统和业务管理平台的二次开发基础。

## 项目状态

当前项目已经具备可扩展的 FastAPI + Vue Vben Admin 基础能力，并接入了真实后端 API 与 `web-antd` 前端。

已实现模块：

- 登录认证、当前用户、密码找回、个人资料和密码修改，以及可配置的企业 OIDC 单点登录。
- 系统管理：用户、角色、菜单、部门、岗位、字典，以及 OAuth2/社交登录管理页。
- 基础设施：参数配置、文件管理、存储渠道和上传配置。
- RBAC 权限码、后端权限校验和后端动态菜单。
- 登录日志和操作日志。
- 文件上传、下载、删除、头像上传和文件管理页面。
- 本地和 S3/MinIO 兼容的对象存储、私有文件短期授权下载链接。
- 通知发布和个人消息。

企业 OIDC 的环境变量、账户/角色映射和安全边界见 [企业 OIDC 配置](docs/enterprise-oidc.md)。
- 用户导出、事项导出、事项 CSV 模板和 CSV 导入。
- 数据库表结构驱动的 FastAPI/Vben 模块 ZIP 生成器。
- OpenAPI TypeScript 客户端生成。
- 后端、前端和 Docker Compose CI 工作流。
- Prometheus 指标、就绪检查和告警规则模板。
- v2.0 多租户主链路：共享表租户与成员关系、登录令牌租户上下文、平台租户与套餐管理、安全切换、配额、全系统租户隔离，以及全部、本部门、本部门及下级、本人和自定义部门数据权限。
- 可配置的租户初始化模板，可选择根部门和岗位、字典、参数、存储、消息、短信、邮件等初始数据。
- 独立且默认关闭的 BPM POC，支持流程版本、审批动作、分派表达式、审计、超时标记和租户隔离。

本地已验证：

- 后端 lint：`uv run ruff check app tests`
- 后端测试：`POSTGRES_SERVER=localhost SMTP_HOST='' uv run pytest`
- 前端类型检查：`pnpm -F @vben/web-antd run typecheck`
- 前端构建：`pnpm -F @vben/web-antd run build`
- 前端 E2E：`pnpm frontend:e2e`
- OpenAPI 生成：`pnpm generate:api`
- 浏览器冒烟：管理员菜单加载、`基础设施` 菜单顺序和关键页面可见性

Docker Compose 工作流已配置在 `.github/workflows/docker-compose.yml`。本地 Docker 验证需要提前安装 Docker CLI。

监控与告警接入见 [监控说明](./docs/monitoring.md)。
可选工作流的启用方式、能力边界和许可证注意事项见 [BPM 工作流 POC](./docs/workflows.md)。

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

根目录 `pnpm generate:api` 会直接从当前后端代码导出临时 OpenAPI schema，再生成 TypeScript 文件到 `frontend/apps/web-antd/src/api/generated`，不依赖本机 8000 端口是否已启动。如需指定外部 OpenAPI 地址，可在 `frontend` 目录运行 `OPENAPI_INPUT=... pnpm generate:api`。

## v1.2 基础设施

### S3 / MinIO 对象存储

默认使用本地目录存储。若要使用 S3 或 MinIO，在 `.env` 中设置
`STORAGE_PROVIDER=s3`，并填写 `S3_BUCKET`、访问密钥和端点。项目已经提供
MinIO 服务定义，开发时可运行：

```bash
docker compose --profile storage up --build
```

后端会在 `S3_AUTO_CREATE_BUCKET=true` 时创建缺失的 bucket。私有文件仍先经过
本项目的权限校验；`GET /api/v1/files/{id}/download-url` 会为 S3 文件生成短期授权
下载链接。

### 代码生成

系统管理中的“代码生成”会读取当前数据库表结构，并下载一个包含 FastAPI Schema、
CRUD 路由骨架、Vben API 封装和列表页的 ZIP。生成结果是可审查的起始模块，不会自动
注册路由或覆盖现有模型；按 ZIP 内 README 合并后，再执行 OpenAPI 生成和前端构建。

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
