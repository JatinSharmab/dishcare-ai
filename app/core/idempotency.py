import hashlib
import json
import re
from contextlib import asynccontextmanager
from contextvars import ContextVar

from app.core.audit import audit, insert_audit
from app.core.exceptions import BusinessError
from app.db.database import Database
from app.services.business import (
    BusinessService,
    fetch_all,
    fetch_one,
)
from app.tools.executor import ToolExecutor
from app.tools.registry import TOOLS

approved_action: ContextVar[dict | None] = ContextVar(
    "approved_action",
    default=None,
)


def canonical_json(value) -> str:

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def fingerprint(value) -> str:

    return hashlib.sha256(
        canonical_json(value).encode("utf-8")
    ).hexdigest()


def confirmation_key(
    customer_id: str,
    session_id: str,
    code: str,
) -> str:

    return fingerprint([
        customer_id,
        session_id,
        code.upper(),
    ])


class TransactionDatabase:

    """
    Adapter that lets the existing BusinessService
    participate in an outer database transaction.
    """

    def __init__(self, conn):

        self.conn = conn

    @asynccontextmanager
    async def connection(self):
        yield self.conn

    @asynccontextmanager
    async def transaction(self):
        yield self.conn

    async def fetch_one(
        self,
        query,
        params=(),
    ):

        return await fetch_one(
            self.conn,
            query,
            params,
        )

    async def fetch_all(
        self,
        query,
        params=(),
    ):

        return await fetch_all(
            self.conn,
            query,
            params,
        )


class OperationStore:

    def __init__(
        self,
        db: Database,
    ):

        self.db = db

    async def lookup(
        self,
        customer_id: str,
        key: str,
    ) -> dict | None:

        row = await self.db.fetch_one(
            """
            SELECT response_json
            FROM idempotency_records
            WHERE customer_id = ?
              AND operation_key = ?
            """,
            (customer_id, key),
        )

        if not row:
            return None

        return json.loads(
            row["response_json"]
        )

    async def execute(
        self,
        customer_id: str,
        key: str,
        name: str,
        arguments: dict,
        expected_fee: int | None = None,
    ) -> dict:

        if not re.fullmatch(
            r"[A-Za-z0-9_-]{16,128}",
            key,
        ):

            raise BusinessError(
                422,
                "INVALID_IDEMPOTENCY_KEY",
                "A valid operation key is required",
            )

        request_hash = fingerprint({
            "tool": name,
            "arguments": arguments,
            "expected_fee": expected_fee,
        })

        try:

            async with self.db.transaction() as conn:

                existing = await fetch_one(
                    conn,
                    """
                    SELECT request_hash, response_json
                    FROM idempotency_records
                    WHERE customer_id = ?
                      AND operation_key = ?
                    """,
                    (
                        customer_id,
                        key,
                    ),
                )

                if existing:

                    if (
                        existing["request_hash"]
                        != request_hash
                    ):

                        raise BusinessError(
                            409,
                            "IDEMPOTENCY_CONFLICT",
                            "Operation key was reused with different data",
                        )

                    return {
                        **json.loads(
                            existing["response_json"]
                        ),
                        "replayed": True,
                    }

                # Reuse Phase 1 business methods, but keep
                # all mutations inside this transaction.
                service = BusinessService(
                    TransactionDatabase(conn)
                )

                executor = ToolExecutor(service)
                executor.validate(name, arguments)
                if not TOOLS[name].write:
                    raise BusinessError(403, "WRITE_TOOL_REQUIRED", "Tool cannot be used for a write")

                result = await executor.execute(
                    customer_id,
                    name,
                    arguments,
                    allow_write=True,
                )

                if not result["ok"]:

                    raise BusinessError(
                        409,
                        result["error"]["code"],
                        result["error"]["message"],
                    )

                # Prevent execution at a changed price.
                if expected_fee is not None:

                    actual_fee = result["data"].get(
                        "monthly_fee_paise"
                    )

                    if actual_fee != expected_fee:

                        raise BusinessError(
                            409,
                            "QUOTE_CHANGED",
                            "Subscription price changed; request a new quote",
                        )

                result["operation_id"] = key

                await conn.execute(
                    """
                    INSERT INTO idempotency_records
                    (
                        customer_id,
                        operation_key,
                        request_hash,
                        response_json
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        customer_id,
                        key,
                        request_hash,
                        canonical_json(result),
                    ),
                )

                await insert_audit(
                    conn,
                    customer_id,
                    name,
                    "completed",
                )

                return {
                    **result,
                    "replayed": False,
                }

        except BusinessError as exc:

            # Outer transaction rolls back any partial write.
            await audit(
                self.db,
                customer_id,
                name,
                exc.code,
            )

            raise