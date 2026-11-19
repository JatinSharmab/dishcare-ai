from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


Intent = Literal[
    "balance",
    "recharge",
    "subscription",
    "technical",
    "retention",
    "field_service",
    "human",
    "general",
]

Language = Literal[
    "english",
    "hindi",
    "hinglish",
]


class IntentDecision(BaseModel):

    model_config = ConfigDict(extra="forbid")

    intents: list[Intent] = Field(
        min_length=1,
        max_length=3,
    )

    language: Language


class ChatRequest(BaseModel):

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    message: str = Field(
        min_length=1,
        max_length=2000,
    )

    session_id: UUID | None = None


class ChatResponse(BaseModel):

    session_id: UUID
    answer: str
    intents: list[str]
    language: Language
    sources: list[str]

    tool_results: list[dict]

    pending_confirmation: dict | None = None