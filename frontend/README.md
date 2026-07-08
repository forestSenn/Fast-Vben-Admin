# Fast Vben Admin Frontend

This directory contains the Vue Vben Admin based frontend used by Fast Vben Admin.

## Main App

- Package: `@vben/web-antd`
- Source: `apps/web-antd`
- Framework: Vue 3, Vite, TypeScript, Pinia, Vue Router, Ant Design Vue

## Development

```bash
pnpm install
pnpm dev
```

## Checks

```bash
pnpm -F @vben/web-antd run typecheck
pnpm -F @vben/web-antd run build
```

The generated OpenAPI client lives in `apps/web-antd/src/api/generated`.
From the repository root, run `pnpm generate:api` while the backend OpenAPI
endpoint is available.

## Attribution

This frontend is based on Vue Vben Admin and keeps its MIT license notice in
`LICENSE`.
