from pydantic import ValidationError

from app.core.exceptions import BusinessError
from app.schemas.business import TechnicianRequest
from app.services.business import BusinessService
from app.tools.registry import TOOLS


class ToolExecutor:

    def __init__(
        self,
        service: BusinessService,
    ):

        self.service = service

    def validate(
        self,
        name: str,
        arguments: dict,
    ) -> dict:

        if name not in TOOLS:
            raise BusinessError(
                400,
                "UNKNOWN_TOOL",
                "Requested tool is not registered",
            )

        try:

            validated = TOOLS[name].schema.model_validate(
                arguments
            )

            return validated.model_dump(
                mode="json"
            )

        except ValidationError:

            raise BusinessError(
                422,
                "INVALID_TOOL_ARGUMENTS",
                "Required tool information is missing or invalid",
            ) from None

    async def execute(
        self,
        customer_id: str,
        name: str,
        arguments: dict,
        *,
        allow_write: bool = False,
    ) -> dict:

        try:

            args = self.validate(
                name,
                arguments,
            )

            if TOOLS[name].write and not allow_write:
                raise BusinessError(
                    403,
                    "CONFIRMATION_REQUIRED",
                    "Customer confirmation is required",
                )

            service = self.service

            if name == "get_catalog":

                data = await service.get_catalog()

            elif name == "cancel_subscription":

                data = await service.cancel_subscription(
                    customer_id,
                    confirmed=True,
                )

            elif name == "book_technician":

                data = await service.book_technician(
                    customer_id,
                    TechnicianRequest.model_validate(
                        args
                    ),
                )

            else:

                handlers = {
                    "get_balance": service.get_balance,
                    "get_payments": service.get_payments,
                    "verify_payment": service.verify_payment,
                    "get_subscription": service.get_subscription,
                    "add_channel": service.add_channel,
                    "remove_channel": service.remove_channel,
                    "change_pack": service.change_pack,
                    "get_retention_offers": (
                        service.get_retention_offers
                    ),
                    "create_complaint": (
                        service.create_complaint
                    ),
                    "get_complaints": service.get_complaints,
                    "get_complaint": service.get_complaint,
                    "get_bookings": service.get_bookings,
                    "escalate": service.escalate,
                }

                handler = handlers[name]

                data = await handler(
                    customer_id,
                    **args,
                )

            return {
                "tool": name,
                "ok": True,
                "data": data,
            }

        except BusinessError as exc:

            return {
                "tool": name,
                "ok": False,
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                },
            }


async def verify_write(
    executor: ToolExecutor,
    customer_id: str,
    name: str,
    arguments: dict,
    result: dict,
) -> bool:

    if not result.get("ok"):
        return False

    service = executor.service
    data = result["data"]

    if name in {
        "add_channel",
        "remove_channel",
        "change_pack",
        "cancel_subscription",
    }:

        current = await service.get_subscription(
            customer_id
        )

        channels = {
            channel["channel_code"]
            for channel in current["channels"]
        }

        if name == "add_channel":
            return arguments["channel_code"] in channels

        if name == "remove_channel":
            return arguments["channel_code"] not in channels

        if name == "change_pack":
            return (
                current["pack_code"]
                == arguments["pack_code"]
            )

        return current["status"] == "cancelled"

    if name == "book_technician":

        bookings = await service.get_bookings(
            customer_id
        )

        return any(
            booking["booking_id"] == data["booking_id"]
            and booking["status"] == "booked"
            and booking["visit_date"] == arguments["visit_date"]
            and booking["slot"] == arguments["slot"]
            for booking in bookings
        )

    if name in {
        "create_complaint",
        "escalate",
    }:

        complaint = await service.get_complaint(
            customer_id,
            data["complaint_id"],
        )

        return (
            complaint["complaint_id"]
            == data["complaint_id"]
        )

    return False