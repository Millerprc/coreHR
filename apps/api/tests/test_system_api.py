from httpx import ASGITransport, AsyncClient

from hris.main import create_app


async def test_health_live_returns_ok() -> None:
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["X-Trace-ID"]


async def test_module_registry_exposes_three_business_phases() -> None:
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/system/modules")

    assert response.status_code == 200
    payload = response.json()
    assert [item["phase"] for item in payload["items"]] == [1, 2, 3]
    assert all(item["status"] == "slice_available" for item in payload["items"])

