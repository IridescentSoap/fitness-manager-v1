from fastapi.testclient import TestClient


def test_health_endpoint_returns_ok(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert "data" in payload
    data = payload["data"]
    assert data["status"] == "ok"
    assert data["timezone"] == "Asia/Shanghai"
    assert data["version"]
    assert data["database"]["status"] == "ok"
    assert data["database"]["integrity_check"] == "ok"


def test_health_response_shape_has_no_demo_metrics(client: TestClient) -> None:
    response = client.get("/api/health")
    payload = response.json()["data"]
    # T0 must not ship hardcoded training/weight demo metrics.
    forbidden = {
        "completed_sessions",
        "training_days",
        "plan_completion_rate",
        "latest_weight",
    }
    assert forbidden.isdisjoint(payload.keys())
