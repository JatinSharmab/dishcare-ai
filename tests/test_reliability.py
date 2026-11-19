from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from test_business import auth_headers, client

BASE = "/api/v1/customers/CUST001/technicians"


def booking():
    return {
        "visit_date": str(date.today() + timedelta(days=1)),
        "slot": "09:00-12:00",
        "issue": "No signal from the receiver",
    }


def test_booking_recovers_after_commit_timeout(client):
    settings = client.app.state.reliability
    settings.technician_failure_mode = "timeout_after_commit"
    settings.upstream_timeout_seconds = 0.12
    client.app.state.technician_client.timeout = 0.10
    headers = {**auth_headers(client), "Idempotency-Key": "test-booking-123456"}
    first = client.post(BASE, headers=headers, json=booking())
    second = client.post(BASE, headers=headers, json=booking())
    assert first.status_code == second.status_code == 200, first.text
    assert first.json() == second.json()
    conflict = client.post(BASE, headers=headers, json={**booking(), "issue": "Other fault"})
    assert conflict.status_code == 409
    assert len(client.get(BASE, headers=headers).json()) == 1


def test_concurrent_same_booking(client):
    headers = {**auth_headers(client), "Idempotency-Key": "test-concurrent-123456"}
    with ThreadPoolExecutor(max_workers=2) as threads:
        responses = list(threads.map(lambda _: client.post(BASE, headers=headers, json=booking()), range(2)))
    assert [r.status_code for r in responses] == [200, 200]
    assert responses[0].json() == responses[1].json()


def test_outage_opens_circuit(client):
    client.app.state.reliability.technician_failure_mode = "always_fail"
    client.app.state.technician_client.breaker.failure_threshold = 1
    headers = {**auth_headers(client), "Idempotency-Key": "test-unavailable-123456"}
    first = client.post(BASE, headers=headers, json=booking())
    assert first.json()["error"]["code"] == "BOOKING_UNCERTAIN"
    second = client.post(BASE, headers=headers, json=booking())
    assert second.json()["error"]["code"] == "CIRCUIT_OPEN"


def test_rate_limit(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app

    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")
    with TestClient(create_app(Settings(
        app_env="test", database_path=tmp_path / "limit.db", seed_demo_data=False,
        jwt_secret="test-secret-for-local-pytest-only-123456789",
    ))) as client:
        assert client.get("/health").status_code == 200
        blocked = client.get("/health")
        assert blocked.status_code == 429
        assert int(blocked.headers["Retry-After"]) > 0
