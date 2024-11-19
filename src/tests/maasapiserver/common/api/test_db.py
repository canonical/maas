from typing import AsyncIterator

from fastapi import FastAPI
from httpx import AsyncClient
import pytest
from pytest_mock import MockerFixture
from sqlalchemy import (
    Column,
    insert,
    Integer,
    MetaData,
    select,
    Table,
    Text,
    update,
)
from sqlalchemy.ext.asyncio import AsyncConnection
from starlette.requests import Request

from maasapiserver.common.api.base import API, Handler, handler
from maasapiserver.main import create_app
from maasapiserver.settings import Config
from maasservicelayer.db import Database

METADATA = MetaData()


TestTable = Table(
    "testing",
    METADATA,
    Column("id", Integer, primary_key=True),
    Column("name", Text),
)


class MyException(Exception):
    """Boom"""


@pytest.fixture
async def insert_app(
    test_config: Config,
    db: Database,
    db_connection: AsyncConnection,
    mocker: MockerFixture,
) -> FastAPI:

    class InsertHandler(Handler):
        @handler(path="/success", methods=["GET"])
        async def success(self, request: Request) -> None:
            await request.state.context.get_connection().execute(
                insert(TestTable).values(id=42, name="default")
            )

        @handler(path="/failure", methods=["GET"])
        async def fail(self, request: Request) -> None:
            await request.state.context.get_connection().execute(
                insert(TestTable).values(id=42)
            )
            raise MyException("boom")

    api_app = await create_app(config=test_config, db=db)
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
        response = await insert_client.get("/insert/failure")
        assert response.status_code == 500

        async with db_connection.begin():
            ids = await db_connection.scalars(select(TestTable.c.id))
        assert list(ids) == []

    async def test_isolation_level(
        self,
        insert_client: AsyncClient,
        db: Database,
        db_connection: AsyncConnection,
    ) -> None:
        response = await insert_client.get("/insert/success")
        assert response.status_code == 200

        second_db_connection = await db.engine.connect()

        async with db_connection.begin():
            async with second_db_connection.begin():
                assert (
                    await db_connection.execute(
                        select(TestTable.c.name).where(TestTable.c.id == 42)
                    )
                ).first().name == "default"
                await second_db_connection.execute(
                    update(TestTable)
                    .where(TestTable.c.id == 42)
                    .values(name="new value")
                )
            assert (
                await db_connection.execute(
                    select(TestTable.c.name).where(TestTable.c.id == 42)
                )
            ).first().name == "default"
