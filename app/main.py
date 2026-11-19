import logging
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.business import router as business_router
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

        logger.info("DishCare AI initialized")

        yield

        logger.info("DishCare AI stopped")

    app = FastAPI(
        title="DishCare AI",
        description=(
            "Authenticated AI-ready customer support "
            "backend for a simulated DTH provider"
        ),
        version="0.1.0",
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
            "service": request.app.state.settings.app_name,
            "version": "0.1.0",
            "database": "connected",
        }

    app.include_router(auth_router)
    app.include_router(business_router)

    return app


app = create_app()