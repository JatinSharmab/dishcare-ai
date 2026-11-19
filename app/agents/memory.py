import asyncio
from uuid import UUID, uuid4

from app.core.safeguards import detects_injection
from app.schemas.conversation import ChatResponse


class ChatEngine:

    def __init__(
        self,
        graph,
    ):

        self.graph = graph

        # Single-process concurrency protection.
        self.locks = [asyncio.Lock() for _ in range(64)]

    async def chat(
        self,
        customer_id: str,
        message: str,
        session_id: UUID | None = None,
    ) -> ChatResponse:

        session_id = session_id or uuid4()

        if detects_injection(message):
            return ChatResponse(
                session_id=session_id,
                answer="I can help with authorized DishCare account and support requests.",
                intents=[], language="english", sources=[], tool_results=[],
                pending_confirmation=None,
            )

        thread_id = (
            f"{customer_id}:{session_id}"
        )

        config = {
            "configurable": {
                "thread_id": thread_id,
            },
            "recursion_limit": 15,
        }

        async with self.locks[hash(thread_id) % len(self.locks)]:

            result = await self.graph.ainvoke(
                {
                    "customer_id": customer_id,
                    "session_id": str(session_id),
                    "message": message,
                },
                config=config,
            )

        sources = sorted({
            doc["source"]
            for doc in result.get(
                "documents", []
            )
        })

        return ChatResponse(
            session_id=session_id,
            answer=result["answer"],
            intents=result.get("intents", []),
            language=result.get(
                "language",
                "english",
            ),
            sources=sources,
            tool_results=result.get(
                "tool_results", []
            ),
            pending_confirmation=result.get(
                "pending_confirmation"
            ),
        )