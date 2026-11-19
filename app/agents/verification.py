import json

from app.agents.state import AgentState
from app.config import Settings
from app.core.exceptions import BusinessError
from app.llm.provider import LLMProvider
from app.prompts.loader import load_prompt


def confirmation_message(
    pending: dict,
    language: str,
) -> str:

    tool = pending["tool"]

    arguments = json.dumps(
        pending["arguments"],
        ensure_ascii=False,
        default=str,
    )

    command = f"CONFIRM {pending['code']}"

    fee = pending.get(
        "new_monthly_fee_paise"
    )

    fee_text = ""

    if fee is not None:

        fee_text = (
            f"\nNew configured monthly fee: "
            f"INR {fee / 100:.2f}"
        )

    if language == "hindi":

        introduction = (
            "इस बदलाव को अभी लागू नहीं किया गया है।"
            " पुष्टि के लिए नीचे दिया गया कोड भेजें।"
        )

    elif language == "hinglish":

        introduction = (
            "Ye action abhi execute nahi hua hai. "
            "Confirm karne ke liye neeche diya code bhejiye."
        )

    else:

        introduction = (
            "This action has not been executed yet. "
            "Please confirm the following operation."
        )

    return (
        f"{introduction}\n"
        f"Action: {tool}\n"
        f"Details: {arguments}"
        f"{fee_text}\n"
        f"Reply: {command}\n"
        "Expires in 5 minutes. Reply CANCEL to discard."
    )


def verified_action_message(
    result: dict,
    language: str,
) -> str:

    if not result.get("ok"):

        error = result.get("error", {})

        return (
            "Operation failed: "
            + error.get(
                "message",
                "Unable to complete request",
            )
        )

    if not result.get("verified"):

        return (
            "The operation returned a result, but its final "
            "business state could not be verified. "
            "Please check its status before retrying."
        )

    data = result["data"]

    if language == "hindi":
        prefix = "आपका अनुरोध सफलतापूर्वक पूरा हो गया है।"

    elif language == "hinglish":
        prefix = "Aapka request successfully complete ho gaya hai."

    else:
        prefix = "Your requested operation has been completed and verified."

    if result["tool"] == "book_technician":

        return (
            f"{prefix}\n"
            f"Booking ID: {data['booking_id']}\n"
            f"Date: {data['visit_date']}\n"
            f"Slot: {data['slot']}"
        )

    if result["tool"] in {
        "create_complaint",
        "escalate",
    }:

        return (
            f"{prefix}\n"
            f"Ticket ID: {data['complaint_id']}\n"
            f"Status: {data['status']}"
        )

    return (
        f"{prefix}\n"
        f"Action: {result['tool']}\n"
        f"Subscription status: {data.get('status')}\n"
        f"Monthly fee: INR "
        f"{data.get('monthly_fee_paise', 0) / 100:.2f}"
    )


def make_verification(
    llm: LLMProvider,
    settings: Settings,
):

    async def verification(
        state: AgentState,
    ) -> dict:

        results = state.get(
            "tool_results", []
        )

        documents = state.get(
            "documents", []
        )

        notes = state.get(
            "notes", []
        )

        language = state.get(
            "language", "english"
        )

        pending = state.get(
            "pending_confirmation"
        )

        if "confirm" in state.get("intents", []):

            answer = (
                verified_action_message(
                    results[-1],
                    language,
                )
                if results
                else "No confirmed operation was executed."
            )

        else:

            context = json.dumps(
                {
                    "customer_message": state["message"],
                    "language": language,
                    "tool_results": results,
                    "retrieved_documents": documents,
                    "notes": notes,
                    "action_awaiting_confirmation": (
                        pending is not None
                    ),
                },
                ensure_ascii=False,
                default=str,
            )

            try:

                answer = await llm.generate(
                    load_prompt(
                        settings.prompt_version,
                        "response",
                    ),
                    context,
                )

            except BusinessError:

                answer = (
                    "I could not generate a complete response. "
                    "Verified business information is included "
                    "in the API tool results."
                )

            if pending:

                answer += (
                    "\n\n"
                    + confirmation_message(
                        pending,
                        language,
                    )
                )

        history = (
            state.get("history", [])
            + [
                {
                    "role": "user",
                    "content": state["message"],
                },
                {
                    "role": "assistant",
                    "content": answer,
                },
            ]
        )[-12:]

        return {
            "answer": answer,
            "history": history,
            "confirmed_action": None,
        }

    return verification