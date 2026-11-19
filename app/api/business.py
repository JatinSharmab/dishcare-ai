from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.security import require_customer
from app.db.database import Database, get_db
from app.schemas.business import (
    BalanceResponse,
    CancellationRequest,
    CatalogResponse,
    ChannelRequest,
    ComplaintRequest,
    ComplaintResponse,
    CustomerResponse,
    EscalationRequest,
    PackRequest,
    PaymentResponse,
    RetentionOfferResponse,
    SubscriptionResponse,
    TechnicianRequest,
    TechnicianResponse,
)
from app.services.business import BusinessService

router = APIRouter(
    prefix="/api/v1/customers",
)


def get_service(
    db: Annotated[Database, Depends(get_db)],
) -> BusinessService:

    return BusinessService(db)


CustomerID = Annotated[
    str,
    Depends(require_customer),
]

Service = Annotated[
    BusinessService,
    Depends(get_service),
]


# ----------------------------------
# CRM
# ----------------------------------

@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    tags=["CRM"],
)
async def get_customer(
    customer_id: CustomerID,
    service: Service,
):
    return await service.get_customer(customer_id)


# ----------------------------------
# BILLING
# ----------------------------------

@router.get(
    "/{customer_id}/balance",
    response_model=BalanceResponse,
    tags=["Billing"],
)
async def get_balance(
    customer_id: CustomerID,
    service: Service,
):
    return await service.get_balance(customer_id)


@router.get(
    "/{customer_id}/payments",
    response_model=list[PaymentResponse],
    tags=["Billing"],
)
async def get_payments(
    customer_id: CustomerID,
    service: Service,
):
    return await service.get_payments(customer_id)


@router.get(
    "/{customer_id}/payments/{payment_id}",
    response_model=PaymentResponse,
    tags=["Billing"],
)
async def verify_payment(
    payment_id: str,
    customer_id: CustomerID,
    service: Service,
):
    return await service.verify_payment(
        customer_id,
        payment_id,
    )


# ----------------------------------
# CATALOG
# ----------------------------------

@router.get(
    "/{customer_id}/catalog",
    response_model=CatalogResponse,
    tags=["Subscriptions"],
)
async def get_catalog(
    customer_id: CustomerID,
    service: Service,
):
    return await service.get_catalog()


# ----------------------------------
# SUBSCRIPTIONS
# ----------------------------------

@router.get(
    "/{customer_id}/subscription",
    response_model=SubscriptionResponse,
    tags=["Subscriptions"],
)
async def get_subscription(
    customer_id: CustomerID,
    service: Service,
):
    return await service.get_subscription(customer_id)


@router.put(
    "/{customer_id}/subscription/pack",
    response_model=SubscriptionResponse,
    tags=["Subscriptions"],
)
async def change_pack(
    payload: PackRequest,
    customer_id: CustomerID,
    service: Service,
):
    return await service.change_pack(
        customer_id,
        payload.pack_code,
    )


@router.put(
    "/{customer_id}/subscription/channels",
    response_model=SubscriptionResponse,
    tags=["Subscriptions"],
)
async def add_channel(
    payload: ChannelRequest,
    customer_id: CustomerID,
    service: Service,
):
    return await service.add_channel(
        customer_id,
        payload.channel_code,
    )


@router.delete(
    "/{customer_id}/subscription/channels/{channel_code}",
    response_model=SubscriptionResponse,
    tags=["Subscriptions"],
)
async def remove_channel(
    channel_code: str,
    customer_id: CustomerID,
    service: Service,
):
    return await service.remove_channel(
        customer_id,
        channel_code,
    )


@router.post(
    "/{customer_id}/subscription/cancel",
    response_model=SubscriptionResponse,
    tags=["Subscriptions"],
)
async def cancel_subscription(
    payload: CancellationRequest,
    customer_id: CustomerID,
    service: Service,
):
    return await service.cancel_subscription(
        customer_id,
        payload.confirmed,
    )


# ----------------------------------
# RETENTION
# ----------------------------------

@router.get(
    "/{customer_id}/retention-offers",
    response_model=list[RetentionOfferResponse],
    tags=["Retention"],
)
async def get_retention_offers(
    customer_id: CustomerID,
    service: Service,
):
    return await service.get_retention_offers(customer_id)


# ----------------------------------
# COMPLAINTS
# ----------------------------------

@router.post(
    "/{customer_id}/complaints",
    status_code=201,
    response_model=ComplaintResponse,
    tags=["Complaints"],
)
async def create_complaint(
    payload: ComplaintRequest,
    customer_id: CustomerID,
    service: Service,
):
    return await service.create_complaint(
        customer_id,
        payload.category,
        payload.description,
    )


@router.get(
    "/{customer_id}/complaints",
    response_model=list[ComplaintResponse],
    tags=["Complaints"],
)
async def get_complaints(
    customer_id: CustomerID,
    service: Service,
):
    return await service.get_complaints(customer_id)


@router.get(
    "/{customer_id}/complaints/{complaint_id}",
    response_model=ComplaintResponse,
    tags=["Complaints"],
)
async def get_complaint(
    complaint_id: str,
    customer_id: CustomerID,
    service: Service,
):
    return await service.get_complaint(
        customer_id,
        complaint_id,
    )


# ----------------------------------
# FIELD SERVICE
# ----------------------------------

@router.post(
    "/{customer_id}/technicians",
    response_model=TechnicianResponse,
    tags=["Field Service"],
)
async def book_technician(
    payload: TechnicianRequest,
    customer_id: CustomerID,
    service: Service,
):
    return await service.book_technician(
        customer_id,
        payload,
    )


@router.get(
    "/{customer_id}/technicians",
    response_model=list[TechnicianResponse],
    tags=["Field Service"],
)
async def get_bookings(
    customer_id: CustomerID,
    service: Service,
):
    return await service.get_bookings(customer_id)


# ----------------------------------
# HUMAN ESCALATION
# ----------------------------------

@router.post(
    "/{customer_id}/escalations",
    status_code=201,
    response_model=ComplaintResponse,
    tags=["Human Escalation"],
)
async def escalate(
    payload: EscalationRequest,
    customer_id: CustomerID,
    service: Service,
):
    return await service.escalate(
        customer_id,
        payload.summary,
    )