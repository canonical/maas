from contextlib import asynccontextmanager
from os.path import abspath
import random
import string
from typing import Any, AsyncIterator, Iterator, Type, TypeVar

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.operators import ColumnOperators

from maasapiserver.common.middlewares.db import TransactionMiddleware
from maasapiserver.settings import Config, DatabaseConfig
from maasservicelayer.db import Database
from maasservicelayer.db.tables import METADATA
from maastesting.pytest.database import cluster_stash


@pytest.fixture
def test_config(
    request: pytest.FixtureRequest, ensuremaasdb: str
) -> Iterator[Config]:
    """Set up the test config schema."""
    yield Config(
        db=DatabaseConfig(ensuremaasdb, host=abspath("db/")),
        debug_queries=request.config.getoption("sqlalchemy_debug"),
        debug=True,
    )


@pytest.fixture
async def db(
    request: pytest.FixtureRequest, test_config: Config
) -> Iterator[Database]:
    db = Database(test_config.db, echo=test_config.debug_queries)
    yield db
    await db.engine.dispose()


@pytest.fixture
def transaction_middleware_class(
    db_connection: AsyncConnection,
) -> Iterator[type]:
    class ConnectionReusingTransactionMiddleware(TransactionMiddleware):
        @asynccontextmanager
        async def get_connection(self) -> AsyncIterator[AsyncConnection]:
            yield db_connection

    yield ConnectionReusingTransactionMiddleware


@pytest.fixture
async def db_connection(
    request: pytest.FixtureRequest, pytestconfig, db: Database
) -> AsyncIterator[AsyncConnection]:
    """A database connection."""
    allow_transactions = (
        request.node.get_closest_marker("allow_transactions") is not None
    )
    conn = await db.engine.connect()
    if allow_transactions:
        try:
            yield conn
        finally:
            await conn.close()
            await db.engine.dispose()
            cluster = pytestconfig.stash[cluster_stash]
            cluster.dropdb(db.config.name)
    else:

        def no_commit():
            raise AssertionError(
                "Commits are not allowed without the allow_transactions marker"
            )

        conn.sync_connection.commit = no_commit
        await conn.begin()
        try:
            yield conn
        finally:
            await conn.rollback()
            await conn.close()


T = TypeVar("T")


class Fixture:
    """Helper for creating test fixtures."""

    def __init__(self, conn: AsyncConnection):
        self.conn = conn

    async def create(
        self,
        table: str,
        data: dict[str, Any] | list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        result = await self.conn.execute(
            METADATA.tables[table].insert().returning("*"), data
        )
        return [row._asdict() for row in result]

    async def get(
        self,
        table: str,
        *filters: ColumnOperators,
    ) -> list[dict[str, Any]]:
        """Take a peak what is in there"""
        table_cls = METADATA.tables[table]
        stmt = table_cls.select().where(*filters)  # type: ignore[arg-type]

        # Provide sorting only if the table has an `id` column.
        if "id" in table:
            stmt = stmt.order_by(table_cls.c.id)

        result = await self.conn.execute(stmt)
        return [row._asdict() for row in result]

    async def get_typed(
        self,
        table: str,
        type_result: Type[T],
        *filters: ColumnOperators,
    ) -> list[T]:
        return [
            type_result(**row) for row in (await self.get(table, *filters))
        ]

    def random_string(self, length: int = 10) -> str:
        return "".join(random.choices(string.ascii_letters, k=length))


@pytest.fixture
def fixture(db_connection: AsyncConnection) -> Iterator[Fixture]:
    yield Fixture(db_connection)
