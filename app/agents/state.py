from typing import TypedDict


class AgentState(TypedDict, total=False):

    # Trusted request identity
    customer_id: str
    session_id: str

    # Current message
    message: str
    language: str

    # Supervisor routing
    intents: list[str]
    remaining: list[str]

    # Trusted runtime evidence
    tool_results: list[dict]
    documents: list[dict]

    # Customer conversation history
    history: list[dict]

    # Human-in-the-loop approval
    pending_confirmation: dict | None
    confirmed_action: dict | None

    # Response generation
    notes: list[str]
    answer: str