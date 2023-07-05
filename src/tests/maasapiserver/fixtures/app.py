from typing import AsyncIterable, Iterable

from fastapi import FastAPI
from httpx import AsyncClient
import pytest

from maasapiserver.main import create_app


@pytest.fixture
def api_app() -> Iterable[FastAPI]:
    """The API application."""
    yield create_app()


@pytest.fixture
async def api_client(api_app: FastAPI) -> AsyncIterable[AsyncClient]:
    """Client for the API."""
    async with AsyncClient(app=api_app, base_url="http://test") as client:
        yield client
