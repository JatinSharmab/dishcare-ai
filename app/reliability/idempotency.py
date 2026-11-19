import hashlib
import json
from pathlib import Path

from app.core.exceptions import BusinessError
from app.db.database import Database


def fingerprint(payload: dict) -> str:

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


async def initialize_reliability(
    db: Database,
):

    schema = (
        Path(__file__).resolve().parents[1]
        / "db"
        / "reliability.sql"
    ).read_text(encoding="utf-8")

    async with db.connection() as conn:

        await conn.executescript(schema)
        await conn.commit()


class OperationLedger:

    def __init__(self, db: Database):
        self.db = db

    async def claim(
        self,
        scope: str,
        key: str,
        payload: dict,
    ) -> dict | None:

        if not key or len(key) > 200:

            raise BusinessError(
                422,
                "INVALID_IDEMPOTENCY_KEY",
                "A valid idempotency key is required",
            )

        request_hash = fingerprint(payload)

        async with self.db.transaction() as conn:

            cursor = await conn.execute(
                """
                SELECT *
                FROM operations
                WHERE scope = ?
                  AND operation_key = ?
                """,
                (scope, key),
            )

            row = await cursor.fetchone()
            await cursor.close()

            if row:

                if row["request_hash"] != request_hash:

                    raise BusinessError(
                        409,
                        "IDEMPOTENCY_CONFLICT",
                        "The key was already used "
                        "with different arguments",
                    )

                if row["status"] == "completed":

                    return json.loads(
                        row["response_json"]
                    )

                raise BusinessError(
                    409,
                    "OUTCOME_UNKNOWN",
                    "Operation is in progress or its outcome "
                    "is uncertain. Check its status before retrying.",
                )

            await conn.execute(
                """
                INSERT INTO operations
                (
                    scope,
                    operation_key,
                    request_hash,
                    status
                )
                VALUES (?, ?, ?, 'processing')
                """,
                (
                    scope,
                    key,
                    request_hash,
                ),
            )

        return None

    async def complete(
        self,
        scope: str,
        key: str,
        result: dict,
    ):

        async with self.db.transaction() as conn:

            await conn.execute(
                """
                UPDATE operations
                SET status = 'completed',
                    response_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE scope = ?
                  AND operation_key = ?
                """,
                (
                    json.dumps(
                        result,
                        ensure_ascii=False,
                        default=str,
                    ),
                    scope,
                    key,
                ),
            )

    async def mark_unknown(
        self,
        scope: str,
        key: str,
    ):

        async with self.db.transaction() as conn:

            await conn.execute(
                """
                UPDATE operations
                SET status = 'unknown',
                    updated_at = CURRENT_TIMESTAMP
                WHERE scope = ?
                  AND operation_key = ?
                  AND status = 'processing'
                """,
                (scope, key),
            )

    async def run(
        self,
        scope: str,
        key: str,
        payload: dict,
        operation,
    ) -> dict:

        existing = await self.claim(
            scope,
            key,
            payload,
        )

        if existing is not None:
            return existing

        try:

            result = await operation()

            await self.complete(
                scope,
                key,
                result,
            )

            return result

        except Exception:

            await self.mark_unknown(
                scope,
                key,
            )

            raise

    async def get_status(
        self,
        scope: str,
        key: str,
    ):

        result = await self.db.fetch_one(
            """
            SELECT status, response_json, updated_at
            FROM operations
            WHERE scope = ?
              AND operation_key = ?
            """,
            (scope, key),
        )

        if not result:

            raise BusinessError(
                404,
                "OPERATION_NOT_FOUND",
                "Operation does not exist",
            )

        return {
            "status": result["status"],
            "result": (
                json.loads(result["response_json"])
                if result["response_json"]
                else None
            ),
            "updated_at": result["updated_at"],
        }