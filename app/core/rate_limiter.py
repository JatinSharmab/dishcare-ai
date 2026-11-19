import asyncio
import hashlib
import math
import time
from contextvars import ContextVar
from uuid import uuid4

from fastapi.responses import JSONResponse


current_request_id = ContextVar(
    "request_id",
    default=None,
)


class FixedWindowLimiter:

    def __init__(
        self,
        window_seconds: float = 60,
        max_keys: int = 10000,
    ):

        self.window_seconds = window_seconds
        self.max_keys = max_keys

        self.entries = {}
        self.lock = asyncio.Lock()

    async def allow(
        self,
        key: str,
        limit: int,
    ) -> tuple[bool, int]:

        async with self.lock:

            now = time.monotonic()

            entry = self.entries.get(key)

            if not entry or now >= entry[1]:

                if len(self.entries) >= self.max_keys:

                    self.entries = {
                        k: v
                        for k, v in self.entries.items()
                        if now < v[1]
                    }

                if (
                    key not in self.entries
                    and len(self.entries) >= self.max_keys
                ):

                    return False, 60

                entry = (
                    0,
                    now + self.window_seconds,
                )

            count, expires_at = entry

            remaining = max(
                1,
                math.ceil(expires_at - now),
            )

            if count >= limit:

                return False, remaining

            self.entries[key] = (
                count + 1,
                expires_at,
            )

            return True, 0


def build_rate_limit_middleware(
    limiter,
    settings,
):

    async def middleware(
        request,
        call_next,
    ):

        request_id = uuid4().hex

        request.state.request_id = request_id

        context_token = current_request_id.set(
            request_id
        )

        try:

            ip = (
                request.client.host
                if request.client
                else "unknown"
            )

            rules = [
                (
                    f"ip:{ip}",
                    settings.rate_limit_per_minute,
                )
            ]

            if request.url.path == "/api/v1/auth/token":

                rules.append(
                    (
                        f"login:{ip}",
                        settings.login_limit_per_minute,
                    )
                )

            authorization = request.headers.get(
                "Authorization", ""
            )

            if authorization.startswith("Bearer "):

                token_hash = hashlib.sha256(
                    authorization.encode("utf-8")
                ).hexdigest()

                rules.append(
                    (
                        f"token:{token_hash}",
                        settings.rate_limit_per_minute,
                    )
                )

            for key, limit in rules:

                allowed, retry_after = (
                    await limiter.allow(key, limit)
                )

                if not allowed:

                    return JSONResponse(
                        status_code=429,
                        content={
                            "error": {
                                "code": "RATE_LIMIT_EXCEEDED",
                                "message": (
                                    "Too many requests. "
                                    "Please try again later."
                                ),
                            }
                        },
                        headers={
                            "Retry-After": str(retry_after),
                            "X-Request-ID": request_id,
                        },
                    )

            response = await call_next(request)

            response.headers["X-Request-ID"] = (
                request_id
            )

            return response

        finally:

            current_request_id.reset(
                context_token
            )

    return middleware