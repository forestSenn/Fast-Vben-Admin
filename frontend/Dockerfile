FROM node:24-alpine AS base

ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"

RUN corepack enable

WORKDIR /app

COPY ./frontend/package.json ./frontend/pnpm-lock.yaml ./frontend/pnpm-workspace.yaml ./
COPY ./frontend/apps ./apps
COPY ./frontend/internal ./internal
COPY ./frontend/packages ./packages
COPY ./frontend/scripts ./scripts
COPY ./frontend/vitest.config.ts ./frontend/turbo.json ./

RUN pnpm install --frozen-lockfile

FROM base AS development

EXPOSE 5173

CMD ["pnpm", "-F", "@vben/web-antd", "run", "dev", "--host", "0.0.0.0"]

FROM base AS build

ARG VITE_GLOB_API_URL=/api/v1
ENV VITE_GLOB_API_URL=$VITE_GLOB_API_URL

RUN pnpm -F @vben/web-antd run build

FROM nginx:1.27-alpine AS production

COPY ./frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/apps/web-antd/dist /usr/share/nginx/html

EXPOSE 80
