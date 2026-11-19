from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

BASE = "/api/v1/customers"


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


def test_health(client):

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_login_and_balance(client):

    response = client.get(
        f"{BASE}/CUST001/balance",
        headers=auth_headers(client),
    )

    assert response.status_code == 200
    assert response.json()["balance_paise"] == 35000


def test_invalid_authentication(client):

    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": "CUST001",
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401

    response = client.get(
        f"{BASE}/CUST001/balance"
    )

    assert response.status_code == 401

    response = client.get(
        f"{BASE}/CUST001/balance",
        headers={
            "Authorization": "Bearer invalid-token"
        },
    )

    assert response.status_code == 401


def test_cross_customer_access(client):

    response = client.get(
        f"{BASE}/CUST002/balance",
        headers=auth_headers(client),
    )

    assert response.status_code == 403


def test_payment_ownership(client):

    headers = auth_headers(client)

    response = client.get(
        f"{BASE}/CUST001/payments/PAY001",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"

    response = client.get(
        f"{BASE}/CUST001/payments/PAY002",
        headers=headers,
    )

    assert response.status_code == 404


def test_successful_recharge_inactive_subscription(client):

    headers = auth_headers(client, "CUST002")

    payment = client.get(
        f"{BASE}/CUST002/payments/PAY002",
        headers=headers,
    )

    subscription = client.get(
        f"{BASE}/CUST002/subscription",
        headers=headers,
    )

    assert payment.json()["status"] == "success"
    assert subscription.json()["status"] == "inactive"

    response = client.put(
        f"{BASE}/CUST002/subscription/channels",
        headers=headers,
        json={"channel_code": "SPORTS_HD"},
    )

    assert response.status_code == 409


def test_failed_recharge(client):

    response = client.get(
        f"{BASE}/CUST003/payments/PAY003",
        headers=auth_headers(client, "CUST003"),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"


def test_duplicate_channel(client):

    headers = auth_headers(client)

    for _ in range(2):

        response = client.put(
            f"{BASE}/CUST001/subscription/channels",
            headers=headers,
            json={"channel_code": "SPORTS_HD"},
        )

        assert response.status_code == 200

    result = response.json()

    channels = [
        channel["channel_code"]
        for channel in result["channels"]
    ]

    assert channels.count("SPORTS_HD") == 1
    assert result["monthly_fee_paise"] == 36900


def test_invalid_arguments(client):

    headers = auth_headers(client)

    response = client.put(
        f"{BASE}/CUST001/subscription/channels",
        headers=headers,
        json={
            "channel_code": "SPORTS_HD",
            "customer_id": "CUST002",
        },
    )

    assert response.status_code == 422

    response = client.put(
        f"{BASE}/CUST001/subscription/channels",
        headers=headers,
        json={"channel_code": "UNKNOWN_CHANNEL"},
    )

    assert response.status_code == 404


def test_change_pack_and_remove_channel(client):

    headers = auth_headers(client)

    response = client.put(
        f"{BASE}/CUST001/subscription/pack",
        headers=headers,
        json={"pack_code": "PREMIUM"},
    )

    assert response.status_code == 200
    assert response.json()["pack_code"] == "PREMIUM"

    response = client.delete(
        f"{BASE}/CUST001/subscription/channels/NEWS_HD",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["channels"] == []
    assert response.json()["monthly_fee_paise"] == 49900


def test_retention_and_cancellation(client):

    headers = auth_headers(client)

    response = client.get(
        f"{BASE}/CUST001/retention-offers",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()[0]["discount_paise"] == 10000

    response = client.post(
        f"{BASE}/CUST001/subscription/cancel",
        headers=headers,
        json={"confirmed": False},
    )

    assert response.status_code == 409

    response = client.post(
        f"{BASE}/CUST001/subscription/cancel",
        headers=headers,
        json={"confirmed": True},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_create_and_track_complaint(client):

    headers = auth_headers(client)

    response = client.post(
        f"{BASE}/CUST001/complaints",
        headers=headers,
        json={
            "category": "technical",
            "description": "No signal on television",
        },
    )

    assert response.status_code == 201

    ticket_id = response.json()["complaint_id"]

    response = client.get(
        f"{BASE}/CUST001/complaints/{ticket_id}",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "open"


def test_duplicate_technician_booking(client):

    headers = auth_headers(client)

    payload = {
        "visit_date": (
            date.today() + timedelta(days=1)
        ).isoformat(),
        "slot": "09:00-12:00",
        "issue": "No signal after restart",
    }

    url = f"{BASE}/CUST001/technicians"

    first = client.post(
        url,
        headers=headers,
        json=payload,
    )

    second = client.post(
        url,
        headers=headers,
        json=payload,
    )

    assert first.status_code == 200
    assert second.status_code == 200

    assert (
        first.json()["booking_id"]
        == second.json()["booking_id"]
    )

    response = client.get(
        url,
        headers=headers,
    )

    assert len(response.json()) == 1


def test_human_escalation(client):

    response = client.post(
        f"{BASE}/CUST001/escalations",
        headers=auth_headers(client),
        json={
            "summary": "Customer requests human assistance"
        },
    )

    assert response.status_code == 201
    assert response.json()["category"] == "human_handoff"
    assert response.json()["status"] == "open"