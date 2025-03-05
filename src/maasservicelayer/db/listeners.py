#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from abc import ABC, abstractmethod
import asyncio
from typing import List

from asyncpg import Connection
from sqlalchemy.ext.asyncio import AsyncEngine


class PostgresListener(ABC):
    def __init__(self, channel: str):
        self.channel = channel

    @abstractmethod
    def handler(
        self, connection: Connection, pid: int, channel: str, payload: str
    ):
        """The handler to be executed when the notification is received on the channel"""
        pass


class PostgresListenersTaskFactory:
    """
    A factory class that provides a convenient method to create a task that asynchronously registers
    PostgreSQL listeners using the provided database and a list of `PostgresListener` objects.
    """

    @classmethod
    async def create(
        cls, db_engine: AsyncEngine, listeners: List[PostgresListener]
    ) -> asyncio.Task:
        """Create a task to register PostgreSQL listeners asynchronously."""

        async def register_listeners():
            async with db_engine.connect() as conn:
                raw_connection = await conn.get_raw_connection()
                for listener in listeners:
                    assert raw_connection.driver_connection is not None
                    await raw_connection.driver_connection.add_listener(
                        listener.channel, listener.handler
                    )

        return asyncio.create_task(register_listeners())
