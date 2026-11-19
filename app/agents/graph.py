from langgraph.graph import END, START, StateGraph

from app.agents.specialized import SpecializedAgents
from app.agents.state import AgentState
from app.agents.supervisor import make_supervisor
from app.agents.verification import make_verification
from app.config import Settings
from app.llm.provider import LLMProvider
from app.rag.vector_store import KnowledgeBase
from app.tools.executor import ToolExecutor


def route_next(
    state: AgentState,
) -> str:

    remaining = state.get(
        "remaining", []
    )

    if not remaining:
        return "verification"

    routes = {
        "balance": "billing",
        "recharge": "billing",
        "subscription": "subscription",
        "technical": "technical",
        "retention": "retention",
        "field_service": "field_service",
        "human": "human",
        "general": "general",
        "confirm": "confirm",
    }

    return routes.get(
        remaining[0],
        "verification",
    )


def build_graph(
    settings: Settings,
    llm: LLMProvider,
    executor: ToolExecutor,
    knowledge: KnowledgeBase,
    checkpointer,
):

    agents = SpecializedAgents(
        llm=llm,
        executor=executor,
        knowledge=knowledge,
        settings=settings,
    )

    builder = StateGraph(AgentState)

    builder.add_node(
        "supervisor",
        make_supervisor(
            llm,
            settings,
        ),
    )

    specialized_nodes = {
        "billing": agents.billing,
        "technical": agents.technical,
        "subscription": agents.subscription,
        "retention": agents.retention,
        "field_service": agents.field_service,
        "human": agents.human,
        "general": agents.general,
        "confirm": agents.confirm,
    }

    for name, node in specialized_nodes.items():

        builder.add_node(
            name,
            node,
        )

    builder.add_node(
        "verification",
        make_verification(
            llm,
            settings,
        ),
    )

    destinations = {
        name: name
        for name in specialized_nodes
    }

    destinations["verification"] = "verification"

    builder.add_edge(
        START,
        "supervisor",
    )

    builder.add_conditional_edges(
        "supervisor",
        route_next,
        destinations,
    )

    for name in specialized_nodes:

        builder.add_conditional_edges(
            name,
            route_next,
            destinations,
        )

    builder.add_edge(
        "verification",
        END,
    )

    return builder.compile(
        checkpointer=checkpointer
    )