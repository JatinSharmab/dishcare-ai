import hashlib
import hmac
import json
from types import SimpleNamespace

from pydantic import SecretStr


def post_event(client, path, event, secret):
    body = json.dumps(event).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return client.post(path, content=body, headers={"X-Hub-Signature-256": "sha256=" + signature})


def test_payment_signature_replay_and_conflict(client):
    client.app.state.reliability.payment_webhook_secret = SecretStr("test-signature")
    path = "/api/v1/webhooks/payments"
    event = {"event_id": "event-one", "payment_id": "PAY001"}
    assert post_event(client, path, event, "wrong").status_code == 401
    assert post_event(client, path, event, "test-signature").json()["duplicate"] is False
    assert post_event(client, path, event, "test-signature").json()["duplicate"] is True
    assert post_event(client, path, {**event, "payment_id": "PAY002"}, "test-signature").status_code == 409


def test_whatsapp_only_processes_registered_sender_once(client):
    state = client.app.state
    state.reliability.whatsapp_enabled = True
    state.reliability.whatsapp_app_secret = SecretStr("test-signature")
    state.reliability.whatsapp_verify_token = SecretStr("test-verify")
    path = "/api/v1/webhooks/whatsapp"
    assert client.get(path, params={
        "hub.mode": "subscribe", "hub.verify_token": "test-verify", "hub.challenge": "42",
    }).text == "42"

    async def register():
        async with state.db.transaction() as conn:
            await conn.execute("UPDATE customers SET phone = '12025550100' WHERE customer_id = 'CUST001'")

    client.portal.call(register)
    calls = []

    async def chat(customer_id, text, session):
        calls.append((customer_id, text, session))
        return SimpleNamespace(answer="Example balance reply")

    state.chat_engine = SimpleNamespace(chat=chat)
    event = {"entry": [{"changes": [{"value": {"messages": [
        {"id": "test-1", "from": "12025550100", "text": {"body": "Balance?"}},
        {"id": "test-2", "from": "12025550101", "text": {"body": "Balance?"}},
    ]}}]}]}
    for _ in range(2):
        assert post_event(client, path, event, "test-signature").status_code == 200
    assert len(calls) == 1
    assert calls[0][:2] == ("CUST001", "Balance?")
