# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

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
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    FIPSViolationException,
)
from maasservicelayer.exceptions.constants import FIPS_VIOLATION_TYPE


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

    @app.get("/fips-violation")
    async def fips_violation() -> None:
        raise FIPSViolationException(
            details=[
                BaseExceptionDetail(
                    type=FIPS_VIOLATION_TYPE,
                    message="FIPS violation occurred.",
                )
            ]
        )

    @app.get("/validation-with-fips")
    async def validation_with_fips() -> None:
        from maasservicelayer.exceptions.catalog import ValidationException

        raise ValidationException(
            details=[
                BaseExceptionDetail(
                    type=FIPS_VIOLATION_TYPE,
                    message="Mixed detail.",
                ),
                BaseExceptionDetail(
                    type="OtherType",
                    message="Other detail.",
                ),
            ]
        )

    @app.get("/validation-without-fips")
    async def validation_without_fips() -> None:
        from maasservicelayer.exceptions.catalog import ValidationException

        raise ValidationException(
            details=[
                BaseExceptionDetail(
                    type="OtherType",
                    message="Non-FIPS detail.",
                )
            ]
        )

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

    async def test_fips_violation_exception(self, client: AsyncClient) -> None:
        response = await client.get("/fips-violation")
        assert response.status_code == 422
        body = response.json()
        assert body["code"] == 422
        assert body["fips_violation"] is True
        assert len(body["details"]) == 1
        assert body["details"][0]["type"] == FIPS_VIOLATION_TYPE

    async def test_validation_with_fips_detail_not_fips_violation(
        self, client: AsyncClient
    ) -> None:
        # A plain ValidationException that happens to carry a FIPS_VIOLATION_TYPE
        # detail does NOT set fips_violation=True — callers must raise
        # FIPSViolationException explicitly for that flag.
        response = await client.get("/validation-with-fips")
        assert response.status_code == 422
        body = response.json()
        assert body["fips_violation"] is False

    async def test_validation_without_fips_detail(
        self, client: AsyncClient
    ) -> None:
        response = await client.get("/validation-without-fips")
        assert response.status_code == 422
        body = response.json()
        assert body["fips_violation"] is False
