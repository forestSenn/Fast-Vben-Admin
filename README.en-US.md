# Fast Vben Admin

[中文](./README.md) | **English**

Fast Vben Admin is a full-stack administration platform foundation. It uses FastAPI for real APIs and authorization boundaries, and the Vue Vben Admin `web-antd` application for the management UI. The project provides extensible implementations for multi-tenancy, RBAC, file storage, auditing, and infrastructure administration.

## Development Notes

- `frontend/apps/web-antd` is the supported frontend application. Other Vben UI applications remain in the repository but are outside this project's maintained feature scope.
- Backend OpenAPI Schema is the source of truth for frontend API types. Run `pnpm generate:api` after API changes; do not hand-edit files in `src/api/generated`.
- The default Docker Compose override is for local hot reload, with the frontend at `http://localhost:5174`. The production Compose combination serves it at `http://localhost:5173`.

## Overview

The project uses a separated frontend and backend architecture. Backend APIs are mounted under `/api/v1`; the frontend builds its navigation and button access from backend-provided menus and permission codes. PostgreSQL, Redis, Mailpit, Adminer, and optional MinIO are included for local development.

## Included Capabilities

### System and Access Control

| Module | Description |
| --- | --- |
| Authentication and account security | JWT login, password recovery and reset, login rate limits and CAPTCHA, QR-code login, TOTP MFA with recovery codes, and profile/password management. |
| Enterprise identity | Configurable enterprise OIDC SSO, account mapping, role mapping, and active-status synchronization. |
| RBAC | Users, roles, menus, permission codes, backend authorization checks, and backend-driven menus. |
| Organization | Departments, posts, user-post assignments, and all/department/department-and-children/self/custom data scopes. |
| Multi-tenancy | Shared-schema isolation, memberships, tenant switching with old-session revocation, plans, quotas, and initialization templates. |
| Audit and messages | Login logs, operation logs, notice publishing, personal messages, and read-state tracking. |

### Infrastructure and Extension

| Module | Description |
| --- | --- |
| Settings and dictionaries | Tenant-scoped system settings, public settings, dictionary types, and dictionary items. |
| File service | File management, avatar upload, size/type limits, local and S3/MinIO-compatible storage, and private pre-signed download URLs. |
| Communication | Management pages for mail and SMS channels, templates, and delivery logs. |
| Code generation | Database-table-driven ZIP starter modules with FastAPI schemas, CRUD route skeletons, Vben API wrappers, and list pages. |
| OpenAPI contract | Export the current backend schema and generate frontend TypeScript types and client code. |
| Business example | The Items module demonstrates CRUD, import/export, CSV templates, and tenant isolation. |
| Observability | Health checks, Prometheus metrics, Sentry integration points, and backend/frontend/Compose CI workflows. |

## Technology Stack

| Technology | Purpose |
| --- | --- |
| Python 3.14, FastAPI, SQLModel, Alembic | Backend services, data models, and database migrations |
| PostgreSQL 17, Redis 8 | Business data, caching, login rate limits, and temporary state |
| Vue 3, Vite, TypeScript, Pinia, Vue Router | Frontend application, state, and routing |
| Vue Vben Admin, Ant Design Vue | The `web-antd` management UI |
| pnpm 11, uv | Frontend and backend dependency tooling |
| Docker Compose, Nginx, Mailpit, Adminer, MinIO | Containerized runtime, mail preview, database administration, and object storage |

## Screenshots

The following screenshots were captured from the default tenant in the local Compose environment.

### Overview

| Sign in | Dashboard |
| --- | --- |
| ![Sign-in page](./docs/assets/preview-login.png) | ![Dashboard](./docs/assets/preview-dashboard.png) |

| User management | Dictionary management |
| --- | --- |
| ![User management](./docs/assets/preview-users.png) | ![Dictionary management](./docs/assets/preview-dictionaries.png) |

### Tenancy and Access Control

| Tenant management | Role management |
| --- | --- |
| ![Tenant management](./docs/assets/preview-tenants.png) | ![Role management](./docs/assets/preview-roles.png) |

| Menu management | File management |
| --- | --- |
| ![Menu management](./docs/assets/preview-menus.png) | ![File management](./docs/assets/preview-files.png) |

### Message Center

| Notice management |
| --- |
| ![Notice management](./docs/assets/preview-notices.png) |

## Getting Started

### Requirements

- Docker Desktop / Docker CLI for the recommended complete local environment
- Python 3.14 and [uv](https://docs.astral.sh/uv/) for standalone backend development
- Node.js 22.18+ and pnpm 11.7+ for standalone frontend development

### Local Docker Compose Development

```powershell
Copy-Item .env.example .env
docker compose up --build
```

| Service | URL |
| --- | --- |
| Frontend development server | http://localhost:5174 |
| Backend API | http://localhost:8000/api/v1 |
| API documentation | http://localhost:8000/docs |
| OpenAPI Schema | http://localhost:8000/api/v1/openapi.json |
| Mail preview | http://localhost:1080 |
| Adminer | http://localhost:8080 |

Default local administrator:

```text
Tenant code: default
Email: admin@example.com
Password: changethis
```

Use the default credentials only locally. Before any non-local deployment, change `SECRET_KEY`, `FIRST_SUPERUSER_PASSWORD`, `POSTGRES_PASSWORD`, the CORS allow list, and storage credentials.

To start MinIO, enable the storage profile:

```powershell
docker compose --profile storage up --build
```

MinIO API: `http://localhost:9000`; console: `http://localhost:9001`.

### Standalone Development

On Windows, the setup helper creates `.env` and installs backend and frontend dependencies:

```powershell
pnpm setup
```

When using a local PostgreSQL server for the backend, override the Docker-only hostname first:

```powershell
$env:POSTGRES_SERVER = 'localhost'
cd backend
uv sync
uv run alembic upgrade head
uv run python app/initial_data.py
uv run fastapi dev app/main.py
```

Start the frontend independently:

```powershell
cd frontend
pnpm install
pnpm -F @vben/web-antd run dev
```

### Common Commands

```powershell
pnpm backend:lint
pnpm backend:test
pnpm frontend:typecheck
pnpm frontend:build
pnpm frontend:e2e
pnpm generate:api
```

The root `pnpm generate:api` command exports a temporary OpenAPI Schema from the current backend source and writes generated files to `frontend/apps/web-antd/src/api/generated`; it does not require a running service on `localhost:8000`.

## Deployment

For production, use the base Compose file with the production override. The frontend is served at `http://localhost:5173`:

```powershell
Copy-Item .env.example .env
docker compose -f compose.yml -f compose.production.yml up -d --build
```

See [deployment](./docs/deployment.md) for production variables, migrations, persistent storage, and S3/MinIO configuration.

## Documentation

- [Local development](./docs/development.md)
- [Deployment](./docs/deployment.md)
- [API contract](./docs/api-contract.md)
- [RBAC](./docs/rbac.md)
- [Module development guide](./docs/module-guide.md)
- [Enterprise OIDC configuration](./docs/enterprise-oidc.md)
- [Monitoring](./docs/monitoring.md)
- [FAQ](./docs/faq.md)

## Acknowledgements

This project builds on ideas and architecture from [Full Stack FastAPI Template](https://github.com/fastapi/full-stack-fastapi-template) and [Vue Vben Admin](https://github.com/vbenjs/vue-vben-admin).
