"""Z0-001 验证：最小 FastAPI 测试。"""
from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_health_live() -> None:
    r = client.get("/health/live")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_health_ready() -> None:
    r = client.get("/health/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ready"}
