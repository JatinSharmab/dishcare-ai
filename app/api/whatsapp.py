import hmac
from uuid import NAMESPACE_URL, uuid5

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, ValidationError

from app.api.webhooks import signed_body
from app.core.exceptions import BusinessError
from app.reliability.idempotency import OperationLedger

router = APIRouter(prefix="/api/v1/webhooks/whatsapp", tags=["Webhooks"])


class Text(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class Message(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    sender: str = Field(alias="from", pattern=r"^[0-9]{8,15}$")
    text: Text | None = None


class ChangeValue(BaseModel):
    messages: list[Message] = Field(default_factory=list)


class Change(BaseModel):
    value: ChangeValue


class Entry(BaseModel):
    changes: list[Change]


class Notification(BaseModel):
    entry: list[Entry]


def whatsapp_settings(request):
    settings = request.app.state.reliability
    if not settings.whatsapp_enabled:
        raise BusinessError(404, "CHANNEL_DISABLED", "WhatsApp is disabled")
    return settings


@router.get("")
async def verify(request: Request):
    settings = whatsapp_settings(request)
    query = request.query_params
    expected = settings.whatsapp_verify_token.get_secret_value()
    if (
        not expected or query.get("hub.mode") != "subscribe"
        or not hmac.compare_digest(expected.encode(), query.get("hub.verify_token", "").encode())
    ):
        raise BusinessError(403, "VERIFICATION_FAILED", "Webhook verification failed")
    return PlainTextResponse(query.get("hub.challenge", ""))


@router.post("")
async def receive(request: Request):
    settings = whatsapp_settings(request)
    body = await signed_body(request, settings.whatsapp_app_secret.get_secret_value())
    try:
        notification = Notification.model_validate_json(body)
    except ValidationError:
        raise BusinessError(422, "INVALID_EVENT", "Invalid WhatsApp notification") from None
    state = request.app.state
    ledger = OperationLedger(state.db)
    for entry in notification.entry:
        for change in entry.changes:
            for message in change.value.messages:
                if message.text is not None:
                    await handle_message(state, ledger, message)
    return {"accepted": True}


async def handle_message(state, ledger, message):
    customers = await state.db.fetch_all(
        "SELECT customer_id FROM customers WHERE phone IN (?, ?) AND enabled = 1 LIMIT 2",
        (message.sender, "+" + message.sender),
    )
    if len(customers) != 1:
        return
    if state.chat_engine is None:
        raise BusinessError(503, "AI_DISABLED", "The AI service is not enabled")
    customer_id = customers[0]["customer_id"]

    async def process():
        reply = await state.chat_engine.chat(
            customer_id, message.text.body, uuid5(NAMESPACE_URL, f"whatsapp:{customer_id}"),
        )
        if state.whatsapp_client is not None:
            await state.whatsapp_client.send(message.sender, reply.answer)
        return {"processed": True}

    await ledger.run(f"whatsapp:{customer_id}", message.id, {"text": message.text.body}, process)
