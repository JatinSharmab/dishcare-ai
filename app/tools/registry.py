from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.schemas.business import (
    ChannelRequest,
    ComplaintRequest,
    EscalationRequest,
    PackRequest,
    StrictRequest,
    TechnicianRequest,
)


class EmptyArguments(StrictRequest):
    pass


class PaymentArguments(StrictRequest):

    payment_id: str = Field(
        min_length=1,
        max_length=100,
    )


class ComplaintArguments(StrictRequest):

    complaint_id: str = Field(
        min_length=1,
        max_length=100,
    )


@dataclass(frozen=True)
class ToolSpec:

    description: str
    schema: type[BaseModel]
    write: bool = False


TOOLS = {

    "get_balance": ToolSpec(
        "Get the authenticated customer's balance",
        EmptyArguments,
    ),

    "get_payments": ToolSpec(
        "List the customer's recharge history",
        EmptyArguments,
    ),

    "verify_payment": ToolSpec(
        "Verify a recharge using its payment ID",
        PaymentArguments,
    ),

    "get_subscription": ToolSpec(
        "Get current subscription and channel details",
        EmptyArguments,
    ),

    "get_catalog": ToolSpec(
        "Get available subscription packs and channels",
        EmptyArguments,
    ),

    "add_channel": ToolSpec(
        "Add a channel using its catalog channel code",
        ChannelRequest,
        True,
    ),

    "remove_channel": ToolSpec(
        "Remove a subscribed channel",
        ChannelRequest,
        True,
    ),

    "change_pack": ToolSpec(
        "Change the customer's subscription pack",
        PackRequest,
        True,
    ),

    "cancel_subscription": ToolSpec(
        "Cancel the subscription after explicit approval",
        EmptyArguments,
        True,
    ),

    "get_retention_offers": ToolSpec(
        "Get eligible personalized retention offers",
        EmptyArguments,
    ),

    "create_complaint": ToolSpec(
        "Create a customer support complaint",
        ComplaintRequest,
        True,
    ),

    "get_complaints": ToolSpec(
        "List the customer's complaints",
        EmptyArguments,
    ),

    "get_complaint": ToolSpec(
        "Track an existing complaint using its ID",
        ComplaintArguments,
    ),

    "book_technician": ToolSpec(
        "Book a technician with future date, slot and issue",
        TechnicianRequest,
        True,
    ),

    "get_bookings": ToolSpec(
        "List the customer's technician bookings",
        EmptyArguments,
    ),

    "escalate": ToolSpec(
        "Create a human support escalation ticket",
        EscalationRequest,
        True,
    ),
}


def tool_definitions(
    names: list[str],
) -> list[dict]:

    return [
        {
            "name": name,
            "description": TOOLS[name].description,
            "parameters": (
                TOOLS[name].schema.model_json_schema()
            ),
        }
        for name in names
    ]