from fastapi.testclient import TestClient

from app.core.cache import redis_cache
from app.core.config import settings


def test_health_status_reports_redis_degradation(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        redis_cache,
        "health_status",
        lambda: {
            "available": False,
            "degraded": True,
            "enabled": True,
            "status": "down",
        },
    )

    response = client.get(f"{settings.API_V1_STR}/utils/health-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["degraded"] is True
    assert payload["database"]["status"] == "up"
    assert payload["redis"]["status"] == "down"
    assert payload["redis"]["enabled"] is True


def test_metrics_exposes_application_http_metrics(client: TestClient) -> None:
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "fast_vben_http_requests_total" in response.text
    assert "fast_vben_http_request_duration_seconds" in response.text


def test_metrics_requires_configured_bearer_token(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "METRICS_AUTH_TOKEN", "metrics-test-token")

    rejected = client.get("/metrics")
    accepted = client.get(
        "/metrics",
        headers={"Authorization": "Bearer metrics-test-token"},
    )

    assert rejected.status_code == 401
    assert accepted.status_code == 200
