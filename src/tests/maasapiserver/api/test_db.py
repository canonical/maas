from typing import Any, AsyncIterator, Iterator

from fastapi import Depends, FastAPI, Request
from httpx import AsyncClient
import pytest
from sqlalchemy import Column, insert, Integer, MetaData, select, Table, text
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.api.base import API, Handler, handler
from maasapiserver.api.db import DatabaseMetricsMiddleware, db_conn
from maasapiserver.db import Database
from maasapiserver.main import create_app

METADATA = MetaData()


TestTable = Table(
    "testing",
    METADATA,
    Column("id", Integer, primary_key=True),
)


class MyException(Exception):
    """Boom"""


@pytest.fixture
async def insert_app(db: Database, db_connection: AsyncConnection) -> FastAPI:
    class InsertHandler(Handler):
        @handler(path="/success", methods=["GET"])
        async def success(
            self, conn: AsyncConnection = Depends(db_conn)
        ) -> None:
            await conn.execute(insert(TestTable).values(id=42))

        @handler(path="/failure", methods=["GET"])
        async def fail(self, conn: AsyncConnection = Depends(db_conn)) -> None:
            await conn.execute(insert(TestTable).values(id=42))
            raise MyException("boom")

    api_app = create_app(db=db)
    api = API(prefix="/insert", handlers=[InsertHandler()])
    api.register(api_app.router)

    async with db_connection.begin():
        await db_connection.run_sync(TestTable.create)
    return api_app


@pytest.fixture
async def insert_client(insert_app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(app=insert_app, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
@pytest.mark.allow_transactions
class TestDBSession:
    async def test_commit(
        self, insert_client: AsyncClient, db_connection: AsyncConnection
    ) -> None:
        response = await insert_client.get("/insert/success")
        assert response.status_code == 200

        async with db_connection.begin():
            ids = await db_connection.scalars(select(TestTable.c.id))
        assert list(ids) == [42]

    async def test_rollback(
        self, insert_client: AsyncClient, db_connection: AsyncConnection
    ) -> None:
        with pytest.raises(MyException):
            await insert_client.get("/insert/failure")

        async with db_connection.begin():
            ids = await db_connection.scalars(select(TestTable.c.id))
        assert list(ids) == []


@pytest.fixture
def query_count_app(
    db: Database,
    db_connection: AsyncConnection,
    transaction_middleware_class: type,
) -> Iterator[FastAPI]:
    app = FastAPI()
    app.add_middleware(DatabaseMetricsMiddleware, db=db)
    app.add_middleware(transaction_middleware_class, db=db)

    @app.get("/{count}")
    async def get(request: Request, count: int) -> Any:
        for _ in range(count):
            await db_connection.execute(text("SELECT 1"))
        return request.state.query_metrics

    yield app


@pytest.fixture
async def query_count_client(
    query_count_app: FastAPI,
) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        app=query_count_app, base_url="http://test"
    ) as client:
        yield client


class TestDatabaseMetricsMiddleware:
    @pytest.mark.parametrize("count", [1, 3])
    async def test_query_metrics(
        self, query_count_client: AsyncClient, count: int
    ) -> None:
        metrics = (await query_count_client.get(f"/{count}")).json()
        assert metrics["count"] == count
        assert metrics["latency"] > 0.0
