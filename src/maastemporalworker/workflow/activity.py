# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncConnection
import structlog
from temporalio.client import Client

from maasservicelayer.context import Context
from maasservicelayer.db import Database
from maasservicelayer.services import CacheForServices, ServiceCollectionV3

UNSET = object()

logger = structlog.getLogger()


class ActivityBase:
    _db: Database

    def __init__(
        self,
        db: Database,
        services_cache: CacheForServices,
        temporal_client: Client,
        connection: AsyncConnection | None = None,
    ):
        self._db = db
        # if provided, will use the single connection and assume a transaction has begun
        self._conn = connection
        self.services_cache = services_cache
        self.temporal_client = temporal_client

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
            context = Context(connection=conn)
            services = await ServiceCollectionV3.produce(
                context=context, cache=self.services_cache
            )
            yield services
            # Run the post commit hooks for temporal services
            await services.temporal.post_commit()
