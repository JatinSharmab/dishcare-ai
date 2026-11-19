from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, ValidationError

from app.core.audit import insert_audit, signature_matches
from app.core.exceptions import BusinessError
from app.reliability.idempotency import fingerprint
from app.services.business import fetch_one

router = APIRouter(prefix="/api/v1/webhooks", tags=["Webhooks"])


async def signed_body(request: Request, secret: str) -> bytes:
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 65536:
            raise BusinessError(413, "PAYLOAD_TOO_LARGE", "Webhook payload is too large")
    if not signature_matches(bytes(body), request.headers.get("X-Hub-Signature-256", ""), secret):
        raise BusinessError(401, "INVALID_SIGNATURE", "Webhook signature failed verification")
    return bytes(body)


class PaymentEvent(BaseModel):
    event_id: str = Field(min_length=1, max_length=128)
    payment_id: str = Field(min_length=1, max_length=128)


@router.post("/payments")
async def payment(request: Request):
    secret = request.app.state.reliability.payment_webhook_secret.get_secret_value()
    body = await signed_body(request, secret)
    try:
        event = PaymentEvent.model_validate_json(body)
    except ValidationError:
        raise BusinessError(422, "INVALID_EVENT", "Invalid payment event") from None
    digest = fingerprint(event.model_dump())
    async with request.app.state.db.transaction() as conn:
        existing = await fetch_one(
            conn, "SELECT request_hash FROM processed_payment_events WHERE event_id = ?",
            (event.event_id,),
        )
        if existing:
            if existing["request_hash"] != digest:
                raise BusinessError(409, "EVENT_CONFLICT", "Event ID was reused")
            return {"accepted": True, "duplicate": True}
        row = await fetch_one(
            conn, "SELECT customer_id, status FROM payments WHERE payment_id = ?", (event.payment_id,),
        )
        if row is None:
            raise BusinessError(404, "PAYMENT_NOT_FOUND", "Unknown payment")
        if row["status"] == "failed":
            raise BusinessError(409, "PAYMENT_STATE_CONFLICT", "Failed payment cannot be settled")
        await conn.execute(
            "UPDATE payments SET status = 'success' WHERE payment_id = ? AND status = 'pending'",
            (event.payment_id,),
        )
        await conn.execute(
            """INSERT INTO processed_payment_events
            (event_id, request_hash, payment_id, response_json) VALUES (?, ?, ?, '{}')""",
            (event.event_id, digest, event.payment_id),
        )
        await insert_audit(conn, row["customer_id"], "payment_webhook", "accepted")
    return {"accepted": True, "duplicate": False}
