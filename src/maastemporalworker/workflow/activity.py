from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.db import Database


class ActivityBase:
    _db: Database

    def __init__(
        self, db: Database, connection: AsyncConnection | None = None
    ):
        self._db = db
        # if provided, will use the single connection and assume a transaction has begun
        self._conn = connection

    @asynccontextmanager
    async def start_transaction(self) -> AsyncIterator[AsyncConnection]:
        if self._conn:
            yield self._conn
        else:
            async with self._db.engine.connect() as conn:
                async with conn.begin():
                    yield conn
