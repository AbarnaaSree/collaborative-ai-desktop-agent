
from fastapi.testclient import TestClient

from app.main import app


def test_list_capabilities_api():
    with TestClient(app) as client:
        response = client.get("/api/v1/capabilities")

    assert response.status_code == 200

    data = response.json()
    agent_types = {item["agent_type"] for item in data}

    assert "website_monitor" in agent_types
    assert "desktop_monitor" in agent_types
    assert "system_report" in agent_types


def test_get_website_monitor_capability_api():
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/capabilities/website_monitor"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["agent_type"] == "website_monitor"
    assert data["name"] == "Website Monitor"
    assert data["requires_desktop_agent"] is False
    assert "check_website_availability" in data["capabilities"]


def test_get_unknown_capability_api():
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/capabilities/unknown_agent"
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Agent capability not found"
