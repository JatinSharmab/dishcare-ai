import asyncio
import hmac
from typing import Annotated

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from app.core.exceptions import BusinessError
from app.schemas.business import TechnicianRequest

router = APIRouter()


class InternalBooking(BaseModel):
    customer_id: str
    booking: TechnicianRequest


@router.post("/internal/technicians", include_in_schema=False)
async def book(
    payload: InternalBooking, request: Request,
    key: Annotated[str, Header(alias="Idempotency-Key")],
):
    expected = request.app.state.service_key
    supplied = request.headers.get("X-Service-Key", "")
    if not hmac.compare_digest(expected.encode(), supplied.encode()):
        raise BusinessError(401, "INVALID_SERVICE_KEY", "Service authentication failed")
    mode = request.app.state.reliability.technician_failure_mode
    if mode == "always_fail":
        raise BusinessError(503, "UPSTREAM_UNAVAILABLE", "Simulated outage")
    result = await request.app.state.operations.execute(
        payload.customer_id, key, "book_technician", payload.booking.model_dump(mode="json"),
    )
    if mode == "timeout_after_commit" and not result["replayed"]:
        await asyncio.sleep(request.app.state.reliability.upstream_timeout_seconds * 2)
    return result["data"]
