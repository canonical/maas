# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.db import Database
from maasservicelayer.services.configurations import ConfigurationsService
from maasservicelayer.services.secrets import (
    SecretsService,
    SecretsServiceFactory,
)

UNSET = object()


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

    async def _get_secret_service(
        self, conn: AsyncConnection
    ) -> SecretsService:
        config = ConfigurationsService(conn)
        return await SecretsServiceFactory.produce(conn, config)

    async def get_simple_secret(
        self, secret: str, default: Any = UNSET
    ) -> Any:
        if self._conn:
            secrets = await self._get_secret_service(self._conn)
            return await secrets.get_simple_secret(secret, default=default)

        async with self.start_transaction() as conn:
            secrets = await self._get_secret_service(conn)
            return await secrets.get_simple_secret(secret, default=default)
