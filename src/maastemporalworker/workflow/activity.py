# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncConnection
import structlog

from maasservicelayer.db import Database
from maasservicelayer.services import ServiceCollectionV3

UNSET = object()

logger = structlog.getLogger()


class ActivityBase:
    _db: Database

    def __init__(
        self, db: Database, connection: AsyncConnection | None = None
    ):
        self._db = db
        # if provided, will use the single connection and assume a transaction has begun
        self._conn = connection

    @asynccontextmanager
    async def _start_transaction(self) -> AsyncIterator[AsyncConnection]:
        """
        Private method. You should always interact with the services provided with the public method start_transaction.
        """
        if self._conn:
            yield self._conn
        else:
            async with self._db.engine.connect() as conn:
                async with conn.begin():
                    yield conn

    @asynccontextmanager
    async def start_transaction(self) -> AsyncIterator[ServiceCollectionV3]:
        async with self._start_transaction() as conn:
            yield await ServiceCollectionV3.produce(conn)
