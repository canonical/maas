#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from asyncpg import Connection
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from maasservicelayer.db import Database
from maasservicelayer.db.listeners import (
    PostgresListener,
    PostgresListenersTaskFactory,
)


class PostgresListenerStub(PostgresListener):
    def __init__(self, channel: str):
        super().__init__(channel)
        self.messages = []

    def handler(
        self, connection: Connection, pid: int, channel: str, payload: str
    ):
        self.messages.append(payload)


class TestPostgresListenersTaskFactory:
    @pytest.mark.asyncio
    async def test_create(self, db: Database):
        first_channel = "sys_test0"
        second_channel = "sys_test1"
        first_stub = PostgresListenerStub(channel=first_channel)
        second_stub = PostgresListenerStub(channel=second_channel)

        register_task = await PostgresListenersTaskFactory.create(
            db.engine, [first_stub, second_stub]
        )
        await register_task

        await self._send_pg_notify(db.engine, first_channel, "test")
        await self._send_pg_notify(db.engine, second_channel, "a")
        await self._send_pg_notify(db.engine, second_channel, "b")

        assert len(first_stub.messages) == 1
        assert first_stub.messages[0] == "test"
        assert len(second_stub.messages) == 2
        assert second_stub.messages == ["a", "b"]

    async def _send_pg_notify(
        self, db_engine: AsyncEngine, channel: str, payload: str
    ):
        async with db_engine.connect() as conn:
            raw_connection = await conn.get_raw_connection()
            await raw_connection.driver_connection.execute(
                f"NOTIFY {channel}, '{payload}'"
            )
