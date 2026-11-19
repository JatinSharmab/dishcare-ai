from uuid import uuid4

import pytest
import pytest_asyncio
from langgraph.checkpoint.sqlite.aio import (
    AsyncSqliteSaver,
)

from app.agents.graph import build_graph
from app.agents.memory import ChatEngine
from app.config import Settings
from app.db.database import Database
from app.db.seed import seed_database
from app.schemas.conversation import IntentDecision
from app.services.business import BusinessService
from app.tools.executor import ToolExecutor


class FakeLLM:

    def __init__(self):

        self.decision = IntentDecision(
            intents=["balance"],
            language="english",
        )

        self.tool_call = None
        self.last_context = ""

    async def structured(
        self,
        system_prompt,
        user_prompt,
        schema,
    ):

        self.last_context = user_prompt

        return self.decision

    async def choose_tool(
        self,
        system_prompt,
        user_prompt,
        tools,
    ):

        return self.tool_call

    async def generate(
        self,
        system_prompt,
        user_prompt,
    ):

        return "Test response based on supplied evidence."


class FakeKnowledgeBase:

    async def retrieve(
        self,
        query,
    ):

        return [
            {
                "source": "troubleshooting.md",
                "text": (
                    "Check HDMI input and restart "
                    "the set-top box."
                ),
                "score": 0.9,
            }
        ]


@pytest_asyncio.fixture
async def environment(tmp_path):

    settings = Settings(
        app_env="test",
        jwt_secret=(
            "test-secret-for-agent-tests-only-123456"
        ),
        database_path=tmp_path / "business.db",
        seed_demo_data=True,
        ai_enabled=False,
        prompt_version="v1",
    )

    db = Database(
        settings.database_path
    )

    await db.initialize()
    await seed_database(db)

    service = BusinessService(db)
    executor = ToolExecutor(service)

    llm = FakeLLM()
    knowledge = FakeKnowledgeBase()

    checkpoint_path = str(
        tmp_path / "checkpoints.sqlite"
    )

    async with AsyncSqliteSaver.from_conn_string(
        checkpoint_path
    ) as saver:

        graph = build_graph(
            settings=settings,
            llm=llm,
            executor=executor,
            knowledge=knowledge,
            checkpointer=saver,
        )

        engine = ChatEngine(graph)

        yield {
            "engine": engine,
            "llm": llm,
            "service": service,
            "executor": executor,
            "settings": settings,
            "knowledge": knowledge,
            "checkpoint_path": checkpoint_path,
        }


@pytest.mark.asyncio
async def test_balance_agent(environment):

    engine = environment["engine"]

    result = await engine.chat(
        "CUST001",
        "What is my balance?",
    )

    assert result.intents == ["balance"]

    assert (
        result.tool_results[0]["data"]["balance_paise"]
        == 35000
    )


@pytest.mark.asyncio
async def test_multi_intent(environment):

    llm = environment["llm"]
    engine = environment["engine"]

    llm.decision = IntentDecision(
        intents=["balance", "technical"],
        language="english",
    )

    result = await engine.chat(
        "CUST001",
        "Check balance and no signal issue",
    )

    tools = [
        item["tool"]
        for item in result.tool_results
    ]

    assert "get_balance" in tools

    assert "get_subscription" in tools

    assert "troubleshooting.md" in result.sources


@pytest.mark.asyncio
async def test_recharge_discrepancy(environment):

    llm = environment["llm"]
    engine = environment["engine"]

    llm.decision = IntentDecision(
        intents=["recharge"],
        language="hinglish",
    )

    result = await engine.chat(
        "CUST002",
        "Recharge successful but subscription inactive",
    )

    results = {
        item["tool"]: item["data"]
        for item in result.tool_results
        if item["ok"]
    }

    assert (
        results["get_payments"][0]["status"]
        == "success"
    )

    assert (
        results["get_subscription"]["status"]
        == "inactive"
    )


@pytest.mark.asyncio
async def test_invalid_tool_arguments(environment):

    executor = environment["executor"]

    result = await executor.execute(
        "CUST001",
        "get_balance",
        {"customer_id": "CUST002"},
    )

    assert result["ok"] is False

    assert (
        result["error"]["code"]
        == "INVALID_TOOL_ARGUMENTS"
    )


@pytest.mark.asyncio
async def test_unknown_tool(environment):

    executor = environment["executor"]

    result = await executor.execute(
        "CUST001",
        "execute_sql",
        {"query": "SELECT * FROM customers"},
    )

    assert result["ok"] is False

    assert (
        result["error"]["code"]
        == "UNKNOWN_TOOL"
    )


@pytest.mark.asyncio
async def test_unconfirmed_write(environment):

    executor = environment["executor"]

    result = await executor.execute(
        "CUST001",
        "add_channel",
        {"channel_code": "SPORTS_HD"},
    )

    assert result["ok"] is False

    assert (
        result["error"]["code"]
        == "CONFIRMATION_REQUIRED"
    )


@pytest.mark.asyncio
async def test_confirmed_channel_addition(environment):

    llm = environment["llm"]
    engine = environment["engine"]
    service = environment["service"]

    llm.decision = IntentDecision(
        intents=["subscription"],
        language="english",
    )

    llm.tool_call = {
        "name": "add_channel",
        "arguments": {
            "channel_code": "SPORTS_HD"
        },
    }

    proposal = await engine.chat(
        "CUST001",
        "Add Sports HD",
    )

    assert proposal.pending_confirmation

    before = await service.get_subscription(
        "CUST001"
    )

    assert before["monthly_fee_paise"] == 31900

    code = proposal.pending_confirmation["code"]

    confirmed = await engine.chat(
        "CUST001",
        f"CONFIRM {code}",
        proposal.session_id,
    )

    assert confirmed.tool_results[0]["ok"]

    assert confirmed.tool_results[0]["verified"]

    assert confirmed.pending_confirmation is None

    after = await service.get_subscription(
        "CUST001"
    )

    assert after["monthly_fee_paise"] == 36900

    # Confirmation cannot be replayed normally.

    replay = await engine.chat(
        "CUST001",
        f"CONFIRM {code}",
        proposal.session_id,
    )

    assert replay.tool_results == []


@pytest.mark.asyncio
async def test_conversation_memory(environment):

    engine = environment["engine"]
    llm = environment["llm"]

    first = await engine.chat(
        "CUST001",
        "My first conversation message",
    )

    await engine.chat(
        "CUST001",
        "And what about that?",
        first.session_id,
    )

    assert (
        "My first conversation message"
        in llm.last_context
    )


@pytest.mark.asyncio
async def test_session_isolation(environment):

    engine = environment["engine"]
    llm = environment["llm"]

    session_id = uuid4()

    await engine.chat(
        "CUST001",
        "Private customer one message",
        session_id,
    )

    result = await engine.chat(
        "CUST002",
        "Check my balance",
        session_id,
    )

    assert (
        "Private customer one message"
        not in llm.last_context
    )

    assert (
        result.tool_results[0]["data"]["balance_paise"]
        == 29900
    )


@pytest.mark.asyncio
async def test_checkpoint_persistence(environment):

    engine = environment["engine"]
    llm = environment["llm"]

    first = await engine.chat(
        "CUST001",
        "Remember this conversation",
    )

    # Open a new graph using the same
    # persistent checkpoint database.

    async with AsyncSqliteSaver.from_conn_string(
        environment["checkpoint_path"]
    ) as saver:

        new_graph = build_graph(
            settings=environment["settings"],
            llm=llm,
            executor=environment["executor"],
            knowledge=environment["knowledge"],
            checkpointer=saver,
        )

        new_engine = ChatEngine(new_graph)

        await new_engine.chat(
            "CUST001",
            "Continue our conversation",
            first.session_id,
        )

        assert (
            "Remember this conversation"
            in llm.last_context
        )