import json
import logging
from time import perf_counter

from app.monitoring.usage import RequestUsage, current_usage

logger = logging.getLogger("dishcare.requests")


def build_tracing_middleware(metrics, prices):
    async def trace(request, call_next):
        started = perf_counter()
        usage = RequestUsage(metrics, prices(request))
        token = current_usage.set(usage)
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            current_usage.reset(token)
            elapsed = perf_counter() - started
            route = getattr(request.scope.get("route"), "path", "unmatched")
            metrics.observe(f"http.{request.method}.{route}", elapsed)
            metrics.increment(f"http.status.{status}")
            logger.info("%s", json.dumps({
                "event": "http_request",
                "request_id": getattr(request.state, "request_id", None),
                "method": request.method, "route": route, "status": status,
                "elapsed_ms": round(elapsed * 1000, 3),
                "llm_calls": usage.calls, "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "unpriced_calls": usage.unpriced_calls,
                "estimated_cost_usd": round(usage.estimated_cost_usd, 9) if not usage.unpriced_calls else None,
            }))
    return trace
