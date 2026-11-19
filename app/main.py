import asyncio
import logging
import sqlite3
from contextlib import (
    AsyncExitStack,
    asynccontextmanager,
)

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.business import router as business_router
from app.api.chat import router as chat_router
from app.config import Settings
from app.core.exceptions import BusinessError
from app.db.database import Database
from app.db.seed import seed_database


logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
) -> FastAPI:

    @asynccontextmanager
    async def lifespan(app: FastAPI):

        runtime_settings = settings or Settings()

        if (
            runtime_settings.app_env == "production"
            and runtime_settings.seed_demo_data
        ):

            raise RuntimeError(
                "Demo data must not be enabled in production"
            )

        db = Database(
            runtime_settings.database_path
        )

        await db.initialize()

        if runtime_settings.seed_demo_data:
            await seed_database(db)

        app.state.settings = runtime_settings
        app.state.db = db
        app.state.chat_engine = None

        async with AsyncExitStack() as stack:

            # Keep Phase 1 automated tests offline.
            if (
                runtime_settings.ai_enabled
                and runtime_settings.app_env != "test"
            ):

                from langgraph.checkpoint.sqlite.aio import (
                    AsyncSqliteSaver,
                )

                from app.agents.graph import build_graph
                from app.agents.memory import ChatEngine
                from app.llm.provider import LLMProvider
                from app.rag.vector_store import KnowledgeBase
                from app.services.business import BusinessService
                from app.tools.executor import ToolExecutor

                llm = LLMProvider(
                    runtime_settings
                )

                stack.push_async_callback(
                    llm.close
                )

                knowledge = await asyncio.to_thread(
                    KnowledgeBase,
                    runtime_settings,
                )

                stack.push_async_callback(
                    asyncio.to_thread,
                    knowledge.close,
                )

                await asyncio.to_thread(
                    knowledge.initialize
                )

                runtime_settings.checkpoint_path.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                checkpointer = (
                    await stack.enter_async_context(
                        AsyncSqliteSaver.from_conn_string(
                            str(
                                runtime_settings.checkpoint_path
                            )
                        )
                    )
                )

                executor = ToolExecutor(
                    BusinessService(db)
                )

                graph = build_graph(
                    settings=runtime_settings,
                    llm=llm,
                    executor=executor,
                    knowledge=knowledge,
                    checkpointer=checkpointer,
                )

                app.state.chat_engine = ChatEngine(
                    graph
                )

                logger.info(
                    "Agentic AI initialized"
                )

            logger.info(
                "DishCare AI initialized"
            )

            yield

        logger.info(
            "DishCare AI stopped"
        )

    app = FastAPI(
        title="DishCare AI",
        description=(
            "Multilingual agentic customer support "
            "backend for a simulated DTH provider"
        ),
        version="0.2.0",
        lifespan=lifespan,
    )

    @app.exception_handler(BusinessError)
    async def business_exception_handler(
        request: Request,
        exc: BusinessError,
    ):

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
        )

    @app.exception_handler(sqlite3.Error)
    async def database_exception_handler(
        request: Request,
        exc: sqlite3.Error,
    ):

        logger.error(
            "Database operation failed: %s",
            type(exc).__name__,
        )

        is_busy = (
            isinstance(exc, sqlite3.OperationalError)
            and (
                "locked" in str(exc).lower()
                or "busy" in str(exc).lower()
            )
        )

        return JSONResponse(
            status_code=503 if is_busy else 500,
            content={
                "error": {
                    "code": (
                        "DATABASE_BUSY"
                        if is_busy
                        else "DATABASE_ERROR"
                    ),
                    "message": (
                        "Database temporarily unavailable"
                        if is_busy
                        else "Internal database error"
                    ),
                }
            },
        )

    @app.get(
        "/health",
        tags=["System"],
    )
    async def health(request: Request):

        await request.app.state.db.fetch_one(
            "SELECT 1"
        )

        return {
            "status": "ok",
            "service": (
                request.app.state.settings.app_name
            ),
            "version": "0.2.0",
            "database": "connected",
            "ai_enabled": (
                request.app.state.chat_engine
                is not None
            ),
        }

    app.include_router(auth_router)
    app.include_router(business_router)
    app.include_router(chat_router)

    return app


app = create_app()