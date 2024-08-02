from typing import Any, AsyncIterator, Iterator

from fastapi import FastAPI, Request
from httpx import AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from starlette.responses import Response

from maasapiserver.v2.constants import V2_API_PREFIX
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.middlewares.services import ServicesMiddleware
from maasservicelayer.db import Database


@pytest.fixture
def services_app(
    db: Database,
    db_connection: AsyncConnection,
    transaction_middleware_class: type,
) -> Iterator[FastAPI]:
    app = FastAPI()
    app.add_middleware(ServicesMiddleware)
    app.add_middleware(transaction_middleware_class, db=db)

    def check_services_are_set(request: Request) -> int:
        """Return 200 if the request context has the services, 404 otherwise"""
        return 200 if hasattr(request.state, "services") else 404

    @app.get(V3_API_PREFIX)
    async def get_v3(request: Request) -> Any:
        return Response(status_code=check_services_are_set(request))

    @app.get(V3_API_PREFIX)
    async def get_v2(request: Request) -> Response:
        return Response(status_code=check_services_are_set(request))

    yield app


@pytest.fixture
async def services_client(services_app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(app=services_app, base_url="http://test") as client:
        yield client


class TestServicesMiddleware:
    async def test_services_are_injected(
        self, services_client: AsyncClient
    ) -> None:
        # v2 endpoints should not have the services in the request context
        v2_response = await services_client.get(V2_API_PREFIX)
        assert v2_response.status_code == 404

        # v3 endpoints should have the services in the request context
        v3_response = await services_client.get(V3_API_PREFIX)
        assert v3_response.status_code == 200
