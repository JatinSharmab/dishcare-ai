import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

@pytest.fixture
def client(tmp_path):

    settings = Settings(
        app_env="test",
        database_path=tmp_path / "test.db",
        jwt_secret="test-secret-for-local-pytest-only-123456789",
        seed_demo_data=True,
    )

    app = create_app(settings)

    with TestClient(app) as test_client:
        yield test_client


def auth_headers(client, customer_id="CUST001"):

    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": customer_id,
            "password": "DemoPass123!",
        },
    )

    assert response.status_code == 200

    token = response.json()["access_token"]

    return {
        "Authorization": f"Bearer {token}"
    }
