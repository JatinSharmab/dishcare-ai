import asyncio
import json
import secrets
import time

from app.agents.state import AgentState
from app.config import Settings
from app.core.exceptions import BusinessError
from app.core.idempotency import confirmation_key
from app.llm.provider import LLMProvider
from app.prompts.loader import load_prompt
from app.rag.vector_store import KnowledgeBase
from app.tools.executor import ToolExecutor, verify_write
from app.tools.registry import TOOLS, tool_definitions


class SpecializedAgents:

    def __init__(
        self,
        llm: LLMProvider,
        executor: ToolExecutor,
        knowledge: KnowledgeBase,
        settings: Settings,
        operations=None,
        technician=None,
    ):

        self.llm = llm
        self.executor = executor
        self.knowledge = knowledge
        self.settings = settings
        self.operations = operations
        self.technician = technician

    def advance(
        self,
        state: AgentState,
        *,
        note: str | None = None,
    ) -> dict:

        updates = {
            "remaining": state["remaining"][1:],
            "tool_results": state.get(
                "tool_results", []
            ).copy(),
            "documents": state.get(
                "documents", []
            ).copy(),
            "notes": state.get(
                "notes", []
            ).copy(),
            "pending_confirmation": state.get(
                "pending_confirmation"
            ),
        }

        if note:
            updates["notes"].append(note)

        return updates

    async def read_tool(
        self,
        state,
        updates,
        name,
        arguments=None,
    ):

        result = await self.executor.execute(
            state["customer_id"],
            name,
            arguments or {},
        )

        updates["tool_results"].append(result)

        return result

    async def retrieve(
        self,
        state,
        updates,
        extra="",
    ):

        query = state["message"] + " " + extra

        documents = await self.knowledge.retrieve(
            query
        )

        updates["documents"].extend(documents)

    async def select_tool(
        self,
        state,
        updates,
        names,
        extra_context=None,
    ):

        context = json.dumps(
            {
                "message": state["message"],
                "history": state.get(
                    "history", []
                )[-8:],
                "context": extra_context,
            },
            ensure_ascii=False,
            default=str,
        )

        call = await self.llm.choose_tool(
            load_prompt(
                self.settings.prompt_version,
                "agent",
            ),
            context,
            tool_definitions(names),
        )

        if call is None:

            updates["notes"].append(
                "Ask for missing details if an action is requested."
            )
            return

        name = call.get("name")

        if name not in names:

            updates["notes"].append(
                "Requested tool is not permitted for this agent."
            )
            return

        try:

            arguments = self.executor.validate(
                name,
                call.get("arguments", {}),
            )

        except BusinessError as exc:

            updates["tool_results"].append({
                "tool": name,
                "ok": False,
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                },
            })

            return

        if not TOOLS[name].write:

            await self.read_tool(
                state,
                updates,
                name,
                arguments,
            )

            return

        await self.propose_write(
            state,
            updates,
            name,
            arguments,
        )

    async def propose_write(
        self,
        state,
        updates,
        name,
        arguments,
    ):

        if updates["pending_confirmation"]:

            updates["notes"].append(
                "Only one write action can be proposed per turn."
            )

            return

        try:

            arguments = self.executor.validate(
                name,
                arguments,
            )

        except BusinessError as exc:

            updates["notes"].append(exc.message)
            return

        preview = {
            "tool": name,
            "arguments": arguments,
        }

        if name in {
            "add_channel",
            "remove_channel",
            "change_pack",
        }:

            service = self.executor.service

            subscription = await service.get_subscription(
                state["customer_id"]
            )

            if subscription["status"] != "active":

                updates["notes"].append(
                    "An active subscription is required."
                )
                return

            catalog = await service.get_catalog()

            total = subscription["monthly_fee_paise"]

            current_channels = {
                item["channel_code"]: item
                for item in subscription["channels"]
            }

            channels = {
                item["channel_code"]: item
                for item in catalog["channels"]
            }

            packs = {
                item["pack_code"]: item
                for item in catalog["packs"]
            }

            if name in {
                "add_channel",
                "remove_channel",
            }:

                code = arguments["channel_code"]

                if code not in channels:

                    updates["notes"].append(
                        "Requested channel does not exist."
                    )
                    return

                fee = channels[code]["monthly_fee_paise"]

                if (
                    name == "add_channel"
                    and code not in current_channels
                ):
                    total += fee

                if (
                    name == "remove_channel"
                    and code in current_channels
                ):
                    total -= fee

            elif name == "change_pack":

                code = arguments["pack_code"]

                if code not in packs:

                    updates["notes"].append(
                        "Requested pack does not exist."
                    )
                    return

                channel_fees = sum(
                    channel["monthly_fee_paise"]
                    for channel in subscription["channels"]
                )

                total = (
                    packs[code]["monthly_fee_paise"]
                    + channel_fees
                )

            preview["new_monthly_fee_paise"] = total

        updates["pending_confirmation"] = {
            **preview,
            "code": secrets.token_hex(4).upper(),
            "expires_at": time.time() + 300,
        }

    # -----------------------------------
    # Billing agent
    # -----------------------------------

    async def billing(
        self,
        state: AgentState,
    ):

        updates = self.advance(state)

        intent = state["remaining"][0]

        if intent == "balance":

            await self.read_tool(
                state,
                updates,
                "get_balance",
            )

        else:

            customer_id = state["customer_id"]
            payments, subscription, documents = await asyncio.gather(
                self.executor.execute(customer_id, "get_payments", {}),
                self.executor.execute(customer_id, "get_subscription", {}),
                self.knowledge.retrieve(state["message"] + " recharge payment subscription activation policy"),
            )
            updates["tool_results"].extend((payments, subscription))
            updates["documents"].extend(documents)

        return updates

    # -----------------------------------
    # Technical agent
    # -----------------------------------

    async def technical(
        self,
        state: AgentState,
    ):

        updates = self.advance(state)

        await self.retrieve(
            state,
            updates,
            "television set top box troubleshooting",
        )

        if not any(
            r["tool"] == "get_subscription"
            and r.get("ok")
            for r in updates["tool_results"]
        ):

            await self.read_tool(
                state,
                updates,
                "get_subscription",
            )

        return updates

    # -----------------------------------
    # Subscription agent
    # -----------------------------------

    async def subscription(
        self,
        state: AgentState,
    ):

        updates = self.advance(state)

        subscription = await self.read_tool(
            state,
            updates,
            "get_subscription",
        )

        catalog = await self.executor.execute(
            state["customer_id"],
            "get_catalog",
            {},
        )

        await self.select_tool(
            state,
            updates,
            [
                "get_catalog",
                "add_channel",
                "remove_channel",
                "change_pack",
            ],
            {
                "subscription": subscription,
                "catalog": catalog,
            },
        )

        return updates

    # -----------------------------------
    # Retention agent
    # -----------------------------------

    async def retention(
        self,
        state: AgentState,
    ):

        updates = self.advance(state)

        offers = await self.read_tool(
            state,
            updates,
            "get_retention_offers",
        )

        await self.retrieve(
            state,
            updates,
            "customer retention cancellation policy",
        )

        await self.select_tool(
            state,
            updates,
            ["cancel_subscription"],
            {"eligible_offers": offers},
        )

        return updates

    # -----------------------------------
    # Field service agent
    # -----------------------------------

    async def field_service(
        self,
        state: AgentState,
    ):

        updates = self.advance(state)

        await self.select_tool(
            state,
            updates,
            [
                "create_complaint",
                "get_complaints",
                "get_complaint",
                "book_technician",
                "get_bookings",
            ],
            {
                "supported_slots": [
                    "09:00-12:00",
                    "12:00-15:00",
                    "15:00-18:00",
                ],
                "current_date": (
                    time.strftime("%Y-%m-%d")
                ),
            },
        )

        return updates

    # -----------------------------------
    # Human escalation node
    # -----------------------------------

    async def human(
        self,
        state: AgentState,
    ):

        updates = self.advance(state)

        await self.propose_write(
            state,
            updates,
            "escalate",
            {
                "summary": state["message"][:1000]
            },
        )

        return updates

    # -----------------------------------
    # General questions
    # -----------------------------------

    async def general(
        self,
        state: AgentState,
    ):

        return self.advance(
            state,
            note=(
                "Answer only within the supported "
                "DTH customer service domain."
            ),
        )

    # -----------------------------------
    # Trusted confirmation execution
    # -----------------------------------

    async def confirm(
        self,
        state: AgentState,
    ):

        updates = self.advance(state)

        action = state.get("confirmed_action")

        if not action:

            updates["notes"].append(
                "No confirmed action exists."
            )

            return updates

        name = action["tool"]
        arguments = action["arguments"]

        customer_id = state["customer_id"]
        if self.operations is None:
            result = await self.executor.execute(customer_id, name, arguments, allow_write=True)
        else:
            key = confirmation_key(customer_id, state["session_id"], action["code"])
            try:
                if name == "book_technician" and self.technician is not None:
                    data = await self.technician.book(customer_id, arguments, key)
                    result = {"tool": name, "ok": True, "data": data}
                else:
                    result = await self.operations.execute(
                        customer_id, key, name, arguments, action.get("new_monthly_fee_paise"),
                    )
            except BusinessError as exc:
                result = {"tool": name, "ok": False, "error": {"code": exc.code, "message": exc.message}}
                if exc.code in {"BOOKING_UNCERTAIN", "CIRCUIT_OPEN", "RECOVERY_IN_PROGRESS"}:
                    updates["pending_confirmation"] = action

        result["verified"] = False

        if result.get("ok"):

            try:

                result["verified"] = await verify_write(
                    self.executor,
                    state["customer_id"],
                    name,
                    arguments,
                    result,
                )

            except Exception:

                updates["notes"].append(
                    "Business outcome verification failed. "
                    "Check the current state before retrying."
                )

        updates["tool_results"].append(result)

        if result["ok"]:
            updates["pending_confirmation"] = None
        updates["confirmed_action"] = None

        return updates