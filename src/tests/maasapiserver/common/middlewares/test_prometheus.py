import re
from typing import AsyncIterator, Iterator

from fastapi import FastAPI
from httpx import AsyncClient
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.api.handlers import APICommon
from maasapiserver.common.constants import API_PREFIX
from maasapiserver.common.middlewares.db import DatabaseMetricsMiddleware
from maasapiserver.common.middlewares.prometheus import PrometheusMiddleware
from maasapiserver.v3.middlewares.context import ContextMiddleware
from maasservicelayer.db import Database


@pytest.fixture
def app(
    db: Database,
    db_connection: AsyncConnection,
    transaction_middleware_class: type,
) -> Iterator[FastAPI]:
    app = FastAPI()
    app.add_middleware(PrometheusMiddleware)
    app.add_middleware(DatabaseMetricsMiddleware, db=db)
    app.add_middleware(transaction_middleware_class, db=db)
    app.add_middleware(ContextMiddleware)
    APICommon.register(app.router)

    @app.get("/{count}")
    async def route(count: int) -> dict[str, int]:
        for _ in range(count):
            await db_connection.execute(text("SELECT 1"))
        return {"count": count}

    yield app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
class TestPrometheusMiddleware:
    @pytest.mark.parametrize("count", [1, 3])
    async def test_queries(self, client: AsyncClient, count: int) -> None:
        response = await client.get(f"/{count}")
        assert response.json() == {"count": count}
        # metrics report matching number of queries for the endpoint
        response = await client.get(f"{API_PREFIX}/metrics")
        assert re.search(
            rf'maas_apiserver_request_query_count_total{{handler="/{{count}}",.*,method="GET",status="200"}} {count}.0',
            response.text,
        )
