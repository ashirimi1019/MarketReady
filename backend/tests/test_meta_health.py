from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import app


def test_meta_health_endpoint_shape():
    client = TestClient(app)
    response = client.get("/meta/health")
    assert response.status_code == 200
    payload = response.json()
    assert "ok" in payload
    assert "database" in payload
    assert "ai" in payload
    assert "storage" in payload
