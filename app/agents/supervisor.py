import json
import time

from app.agents.state import AgentState
from app.config import Settings
from app.llm.provider import LLMProvider
from app.prompts.loader import load_prompt
from app.schemas.conversation import IntentDecision


def make_supervisor(
    llm: LLMProvider,
    settings: Settings,
):

    async def supervisor(
        state: AgentState,
    ) -> dict:

        message = state["message"].strip()

        history = state.get(
            "history", []
        )[-8:]

        pending = state.get(
            "pending_confirmation"
        )

        reset = {
            "tool_results": [],
            "documents": [],
            "notes": [],
            "answer": "",
            "confirmed_action": None,
            "pending_confirmation": None,
        }

        if message.upper().startswith("CONFIRM "):

            if not pending:

                return {
                    **reset,
                    "intents": [],
                    "remaining": [],
                    "notes": [
                        "No action is awaiting confirmation."
                    ],
                }

            expected = (
                f"CONFIRM {pending['code']}"
            )

            if time.time() > pending["expires_at"]:

                return {
                    **reset,
                    "intents": [],
                    "remaining": [],
                    "notes": [
                        "Confirmation expired. Request the action again."
                    ],
                }

            if message.upper() != expected:

                return {
                    **reset,
                    "intents": [],
                    "remaining": [],
                    "pending_confirmation": pending,
                    "notes": [
                        "Incorrect confirmation code."
                    ],
                }

            return {
                **reset,
                "intents": ["confirm"],
                "remaining": ["confirm"],
                "confirmed_action": pending,
            }

        if message.upper() == "CANCEL":

            return {
                **reset,
                "intents": [],
                "remaining": [],
                "notes": [
                    "Pending action was discarded."
                ],
            }

        user_context = json.dumps(
            {
                "history": history,
                "current_message": message,
            },
            ensure_ascii=False,
        )

        decision = await llm.structured(
            load_prompt(
                settings.prompt_version,
                "supervisor",
            ),
            user_context,
            IntentDecision,
        )

        intents = list(
            dict.fromkeys(decision.intents)
        )

        if "human" in intents:
            intents = ["human"]

        return {
            **reset,
            "language": decision.language,
            "intents": intents,
            "remaining": intents.copy(),
        }

    return supervisor