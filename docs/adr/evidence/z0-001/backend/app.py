"""Z0-001 验证：最小 FastAPI 应用。"""
from fastapi import FastAPI

app = FastAPI(title="Z0-001 Verify", version="0.0.1")


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
def ready() -> dict[str, str]:
    return {"status": "ready"}
