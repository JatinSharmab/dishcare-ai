from contextvars import ContextVar
from dataclasses import dataclass, field

from app.monitoring.metrics import Metrics


@dataclass
class RequestUsage:
    metrics: Metrics
    prices: dict = field(default_factory=dict)
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    unpriced_calls: int = 0


current_usage: ContextVar[RequestUsage | None] = ContextVar("current_usage", default=None)


def record_usage(provider, model, response):
    usage = current_usage.get()
    if usage is None:
        return
    if provider == "gemini":
        metadata = getattr(response, "usage_metadata", None)
        prompt = getattr(metadata, "prompt_token_count", 0) or 0
        output = (getattr(metadata, "candidates_token_count", 0) or 0) + (
            getattr(metadata, "thoughts_token_count", 0) or 0
        )
    else:
        metadata = getattr(response, "usage", None)
        prompt = getattr(metadata, "prompt_tokens", 0) or 0
        output = getattr(metadata, "completion_tokens", 0) or 0
    usage.calls += 1
    usage.input_tokens += prompt
    usage.output_tokens += output
    rate = usage.prices.get(model)
    if rate is None or metadata is None:
        usage.unpriced_calls += 1
    else:
        usage.estimated_cost_usd += (prompt * rate[0] + output * rate[1]) / 1_000_000
    usage.metrics.increment(f"llm.{provider}.calls")
    usage.metrics.increment(f"llm.{provider}.input_tokens", prompt)
    usage.metrics.increment(f"llm.{provider}.output_tokens", output)
