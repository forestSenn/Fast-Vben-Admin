# 部署

## Docker Compose

```powershell
Copy-Item .env.example .env
docker compose up --build
```

服务默认端口：

- 前端：`http://localhost:5173`
- 后端：`http://localhost:8000`
- OpenAPI：`http://localhost:8000/api/v1/openapi.json`
- Adminer：`http://localhost:8080`

## 生产环境变量

生产部署前必须修改：

- `SECRET_KEY`
- `FIRST_SUPERUSER_PASSWORD`
- `POSTGRES_PASSWORD`
- `DOMAIN`
- `BACKEND_CORS_ORIGINS`

后端会对默认 `changethis` 值发出安全警告。生产环境建议使用独立 PostgreSQL、HTTPS 反向代理和可靠的文件存储目录。

## 数据库迁移

```bash
cd backend
uv run alembic upgrade head
```

## 文件存储

当前默认使用本地存储，文件元数据保存在 `fileasset` 表中。生产环境需要保证上传目录持久化，并限制可上传类型和大小。
