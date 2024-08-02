from typing import Any, AsyncIterator, Iterator

from fastapi import FastAPI, Request
from httpx import AsyncClient
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.middlewares.db import DatabaseMetricsMiddleware
from maasservicelayer.db import Database


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
