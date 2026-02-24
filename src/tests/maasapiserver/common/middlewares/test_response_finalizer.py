# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import AsyncIterator, Iterator, Optional
from unittest.mock import Mock

from fastapi import FastAPI
from httpx import AsyncClient
from pydantic import BaseModel
import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from starlette.requests import Request
from starlette.responses import Response

from maasapiserver.common.middlewares.response_finalizer import (
    ResponseFinalizerMiddleware,
)
from maasapiserver.v3.auth.cookie_manager import EncryptedCookieManager
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
    app.add_middleware(ResponseFinalizerMiddleware)
    app.state.cookie_manager = Mock(spec=EncryptedCookieManager)

    @app.post("/validate")
    async def validate(request: Request, body: DummyRequest) -> dict:
        request.state.cookie_manager = app.state.cookie_manager
        request.state.cookie_manager.clear_cookie("test_cookie")
        return {}

    yield app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
class TestResponseFinalizerMiddleware:
    async def test_response_finalizer_middleware(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/validate",
            json={"required_property": "value"},
            cookies={"test_cookie": "cookie_value"},
        )
        assert response.status_code == 200
        assert response.cookies.get("test_cookie") is None
        cookie_manager = app.state.cookie_manager
        cookie_manager.bind_response.assert_called_once()
        bound_response = cookie_manager.bind_response.call_args[0][0]
        assert isinstance(bound_response, Response)
