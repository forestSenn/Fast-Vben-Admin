# Fast Vben Admin

[中文](./README.md) | **English**

Fast Vben Admin is a full-stack admin template that combines a FastAPI backend with the Vue Vben Admin `web-antd` frontend. It is designed as a ready-to-extend foundation for admin systems, RBAC permission systems, and business management platforms.

## Status

The project already provides a practical FastAPI + Vue Vben Admin base with real backend APIs and the `web-antd` frontend.

Implemented modules:

- Authentication, current user, password recovery, profile and password update, and configurable enterprise OIDC SSO.
- System management for users, roles, menus, departments, posts, dictionaries, and OAuth2/social admin pages.
- Infrastructure management for settings, file management, storage channels, and upload configuration.
- RBAC permission codes, backend permission checks and backend-driven menu loading.
- Login logs and operation logs.

See [Enterprise OIDC configuration](docs/enterprise-oidc.md) for environment settings, local-account mapping, and security boundaries.
- File upload, download, delete, avatar upload and file management page.
- Local and S3/MinIO-compatible object storage with short-lived private download URLs.
- Notice publishing and personal messages.
- User export, Items export, Items CSV template and CSV import.
- Database-table-driven FastAPI/Vben module ZIP generation.
- OpenAPI TypeScript client generation.
- Backend, frontend and Docker Compose CI workflows.
- v2.0 multi-tenancy with shared-schema tenants and memberships, tenant-bound login context, platform tenant and plan management, safe switching, quotas, system-wide tenant isolation, and all/department/department-and-children/self/custom data scopes.
- Configurable tenant initialization templates for root departments and optional post, dictionary, setting, storage, messaging, SMS, and mail seed data.
- An independent, disabled-by-default BPM POC with versioning, approval actions, assignment expressions, audit trails, timeout markers, and tenant isolation.

See [Optional BPM Workflow POC](./docs/workflows.md) for enablement, scope, and licensing constraints.

Verified locally:

- Backend lint: `uv run ruff check app tests`
- Backend tests: `POSTGRES_SERVER=localhost SMTP_HOST='' uv run pytest`
- Frontend typecheck: `pnpm -F @vben/web-antd run typecheck`
- Frontend build: `pnpm -F @vben/web-antd run build`
- Frontend E2E: `pnpm frontend:e2e`
- OpenAPI generation: `pnpm generate:api`
- Browser smoke check for menu loading, infrastructure ordering, and core page visibility

The Docker Compose workflow is configured in `.github/workflows/docker-compose.yml`. Local Docker verification requires Docker to be installed.

## Tech Stack

- Backend: FastAPI, SQLModel, Alembic, PostgreSQL, JWT, Pytest, uv
- Frontend: Vue 3, Vite, TypeScript, Pinia, Vue Router, Vue Vben Admin, Ant Design Vue, pnpm
- Infrastructure: Docker Compose, Nginx, Mailcatcher/Mailpit, Adminer

## Preview

### Dashboard

![Dashboard preview](./docs/assets/preview-dashboard.png)

### User Management

![User management preview](./docs/assets/preview-users.png)

### Dictionary Management

![Dictionary management preview](./docs/assets/preview-dictionaries.png)

## Quick Start

```bash
cp .env.example .env
docker compose up --build
```

On Windows, the setup helper can create `.env` and install backend/frontend dependencies:

```powershell
pnpm setup
```

Default local URLs:

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs
- OpenAPI schema: http://localhost:8000/api/v1/openapi.json
- Mail preview: http://localhost:1080
- Database admin: http://localhost:8080

Default local administrator:

- Email: `admin@example.com`
- Password: `changethis`

Change all default secrets before any non-local deployment.

## Development

Backend:

```bash
cd backend
uv sync
uv run alembic upgrade head
fastapi dev app/main.py
```

When running backend commands directly against a local PostgreSQL server instead of the Docker Compose database, override the Docker-only host name:

```powershell
$env:POSTGRES_SERVER='localhost'
```

Frontend:

```bash
cd frontend
pnpm install
pnpm dev
```

Useful root commands:

```bash
pnpm backend:lint
pnpm backend:test
pnpm frontend:typecheck
pnpm frontend:build
pnpm frontend:e2e
pnpm generate:api
```

`pnpm generate:api` exports a temporary OpenAPI schema from the current backend code and writes generated TypeScript files to `frontend/apps/web-antd/src/api/generated`, so it does not depend on a running server on port `8000`. Override the schema URL with `OPENAPI_INPUT` from the `frontend` directory when needed.

## More Docs

- `docs/development.md`
- `docs/deployment.md`
- `docs/api-contract.md`
- `docs/rbac.md`
- `docs/module-guide.md`
- `docs/faq.md`

## Reference Projects

This project integrates ideas and code from:

- Full Stack FastAPI Template
- Vue Vben Admin
