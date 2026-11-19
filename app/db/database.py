from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite
from fastapi import Request


class Database:

    def __init__(self, path: Path):
        self.path = path

    @asynccontextmanager
    async def connection(self):
        async with aiosqlite.connect(
            self.path,
            timeout=5,
        ) as conn:

            conn.row_factory = aiosqlite.Row

            await conn.execute("PRAGMA foreign_keys = ON")
            await conn.execute("PRAGMA busy_timeout = 5000")

            yield conn

    async def initialize(self):
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        schema_path = Path(__file__).with_name("schema.sql")
        schema = schema_path.read_text(encoding="utf-8")

        async with self.connection() as conn:
            await conn.execute("PRAGMA journal_mode = WAL")
            await conn.executescript(schema)
            await conn.commit()

    @asynccontextmanager
    async def transaction(self):
        async with self.connection() as conn:
            await conn.execute("BEGIN IMMEDIATE")

            try:
                yield conn
                await conn.commit()

            except BaseException:
                await conn.rollback()
                raise

    async def fetch_one(
        self,
        query: str,
        params: tuple = (),
    ) -> dict | None:

        async with self.connection() as conn, conn.execute(query, params) as cursor:
            row = await cursor.fetchone()

            return dict(row) if row else None

    async def fetch_all(
        self,
        query: str,
        params: tuple = (),
    ) -> list[dict]:

        async with self.connection() as conn, conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()

            return [dict(row) for row in rows]


def get_db(request: Request) -> Database:
    return request.app.state.db
