"""Browser-facing CORS security checks."""

import pytest


@pytest.mark.asyncio
async def test_local_frontend_origin_is_allowed(client):
    response = await client.options(
        "/api/status",
        headers={
            "Origin": "http://localhost:3001",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3001"
    assert response.headers["access-control-allow-credentials"] == "true"


@pytest.mark.asyncio
async def test_unlisted_frontend_origin_is_not_allowed(client):
    response = await client.options(
        "/api/status",
        headers={
            "Origin": "https://malicious.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.asyncio
async def test_public_demo_hostname_cannot_read_owner_http_api(client):
    response = await client.get(
        "/api/status",
        headers={"Host": "demo-api.muxtrail.com"},
    )

    assert response.status_code == 404
