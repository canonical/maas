from typing import AsyncIterator, Iterator, Optional

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from httpx import AsyncClient
from pydantic import BaseModel
import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.middlewares.exceptions import (
    ExceptionHandlers,
    ExceptionMiddleware,
)
from maasservicelayer.db import Database


class DummyRequest(BaseModel):
    optional_property: Optional[str]
    required_property: str


@pytest.fixture
def app(
    db: Database,
    db_connection: AsyncConnection,
    transaction_middleware_class: type,
) -> Iterator[FastAPI]:
    app = FastAPI()
    app.add_middleware(ExceptionMiddleware)
    app.add_exception_handler(
        RequestValidationError, ExceptionHandlers.validation_exception_handler
    )

    @app.post("/validate")
    async def validate(request: DummyRequest) -> dict:
        return {}

    @app.get("/exception")
    async def exception() -> None:
        raise Exception("Unhandled exception.")

    yield app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
class TestExceptionMiddleware:
    async def test_internal_server_error(self, client: AsyncClient) -> None:
        response = await client.get("/exception")
        assert response.status_code == 500
        assert response.json()["code"] == 500


@pytest.mark.asyncio
class TestExceptionHandlers:
    async def test_validation(self, client: AsyncClient) -> None:
        response = await client.post("/validate", data={})
        assert response.status_code == 422
        assert response.json()["code"] == 422
