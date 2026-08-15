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
    assert all(item["status"] == "uat_ready" for item in payload["items"])
    assert all(item["available_capabilities"] for item in payload["items"])
    assert all(item["pending_inputs"] for item in payload["items"])
    assert payload["items"][0]["available_endpoints"][0] == "/api/v1/organizations"


async def test_legacy_workforce_endpoints_are_disabled() -> None:
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        create_organization = await client.post(
            "/api/v1/workforce/organizations",
            json={"code": "888888"},
        )
        create_type = await client.post(
            "/api/v1/workforce/organization-types",
            json={"code": "BU", "name": "业务单元"},
        )
        list_organizations = await client.get("/api/v1/workforce/organizations")

    assert create_organization.status_code == 404
    assert create_type.status_code == 404
    assert list_organizations.status_code == 404
