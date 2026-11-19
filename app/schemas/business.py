from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


# Authentication

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# Customer and billing

class CustomerResponse(BaseModel):
    customer_id: str
    name: str
    phone: str


class BalanceResponse(BaseModel):
    customer_id: str
    balance_paise: int
    currency: Literal["INR"] = "INR"


class PaymentResponse(BaseModel):
    payment_id: str
    customer_id: str
    amount_paise: int
    status: Literal["success", "failed", "pending"]
    created_at: str


# Subscription and channels

class PackResponse(BaseModel):
    pack_code: str
    name: str
    monthly_fee_paise: int


class ChannelResponse(BaseModel):
    channel_code: str
    name: str
    monthly_fee_paise: int


class CatalogResponse(BaseModel):
    packs: list[PackResponse]
    channels: list[ChannelResponse]


class SubscriptionResponse(BaseModel):
    customer_id: str
    pack_code: str
    pack_name: str
    status: Literal["active", "inactive", "cancelled"]
    expiry_date: date
    channels: list[ChannelResponse]
    monthly_fee_paise: int


class ChannelRequest(StrictRequest):
    channel_code: str = Field(
        min_length=1,
        max_length=40,
        pattern=r"^[A-Z0-9_]+$",
    )


class PackRequest(StrictRequest):
    pack_code: str = Field(
        min_length=1,
        max_length=40,
        pattern=r"^[A-Z0-9_]+$",
    )


class CancellationRequest(StrictRequest):
    confirmed: bool = Field(strict=True)


# Complaints

class ComplaintRequest(StrictRequest):
    category: Literal[
        "billing",
        "technical",
        "subscription",
        "other",
    ]

    description: str = Field(
        min_length=5,
        max_length=1000,
    )


class ComplaintResponse(BaseModel):
    complaint_id: str
    customer_id: str
    category: str
    description: str
    status: str
    created_at: str


# Technician booking

class TechnicianRequest(StrictRequest):
    visit_date: date

    slot: Literal[
        "09:00-12:00",
        "12:00-15:00",
        "15:00-18:00",
    ]

    issue: str = Field(
        min_length=5,
        max_length=500,
    )


class TechnicianResponse(BaseModel):
    booking_id: str
    customer_id: str
    visit_date: date
    slot: str
    issue: str
    status: str
    created_at: str


# Customer retention

class RetentionOfferResponse(BaseModel):
    offer_id: str
    customer_id: str
    description: str
    discount_paise: int
    valid_until: date


# Human escalation

class EscalationRequest(StrictRequest):
    summary: str = Field(
        min_length=5,
        max_length=1000,
    )