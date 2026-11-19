import hashlib
import hmac

from app.core.rate_limiter import current_request_id


async def insert_audit(conn, customer_id, action, outcome):
    await conn.execute(
        "INSERT INTO audit_events(actor_ref, action, outcome, request_id) VALUES (?, ?, ?, ?)",
        (hashlib.sha256(customer_id.encode()).hexdigest(), action, outcome, current_request_id.get()),
    )


async def audit(db, customer_id, action, outcome):
    async with db.transaction() as conn:
        await insert_audit(conn, customer_id, action, outcome)


def signature_matches(body: bytes, signature: str, secret: str) -> bool:
    if not secret or not signature.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected.encode(), signature[7:].encode())
