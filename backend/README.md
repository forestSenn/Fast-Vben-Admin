# Fast Vben Admin Backend

FastAPI backend for Fast Vben Admin.

## Development

```bash
uv sync
fastapi dev app/main.py
```

The API is mounted under `/api/v1`.

Useful local URLs:

- API docs: http://localhost:8000/docs
- OpenAPI schema: http://localhost:8000/api/v1/openapi.json
- Health check: http://localhost:8000/api/v1/utils/health-check
