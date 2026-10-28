from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok() -> None:
    for path in ("/api/health", "/health"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "schema_version": "1"}
