import asyncio
import random

import httpx

from app.core.exceptions import BusinessError


class TechnicianClient:
    def __init__(self, client, breaker, timeout):
        self.client = client
        self.breaker = breaker
        self.timeout = timeout

    async def book(self, customer_id, payload, key):
        self.breaker.acquire()
        try:
            for attempt in range(3):
                try:
                    response = await asyncio.wait_for(self.client.post(
                        "/internal/technicians",
                        json={"customer_id": customer_id, "booking": payload},
                        headers={"Idempotency-Key": key},
                    ), timeout=self.timeout)
                    response.raise_for_status()
                    self.breaker.success()
                    return response.json()
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code < 500:
                        self.breaker.success()
                        body = exc.response.json().get("error", {})
                        raise BusinessError(
                            exc.response.status_code, body.get("code", "BOOKING_REJECTED"),
                            body.get("message", "Technician booking rejected"),
                        ) from None
                except (TimeoutError, httpx.TransportError):
                    pass
                if attempt < 2:
                    await asyncio.sleep(random.uniform(0, 0.05 * 2**attempt))
            self.breaker.failure()
            raise BusinessError(503, "BOOKING_UNCERTAIN", "Retry using the same booking key")
        finally:
            self.breaker.release_probe()
