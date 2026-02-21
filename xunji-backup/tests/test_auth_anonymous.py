from fastapi.testclient import TestClient
from app.main import app
import uuid


client = TestClient(app)


def test_anonymous_login_and_upgrade():
    device_id = f"device-{uuid.uuid4().hex}"
    response = client.post("/api/auth/anonymous-login", json={"device_id": device_id})
    assert response.status_code == 200
    data = response.json()
    assert data["access_token"]
    assert data["device_id"] == device_id
    assert data["user_id"]

    username = f"user_{uuid.uuid4().hex[:8]}"
    upgrade_response = client.post(
        "/api/auth/upgrade-account",
        headers={"X-Device-ID": device_id},
        json={"username": username, "password": None},
    )
    assert upgrade_response.status_code == 200
    upgrade_data = upgrade_response.json()
    assert upgrade_data["access_token"]
    assert upgrade_data["username"] == username
    assert upgrade_data["device_id"] == device_id
