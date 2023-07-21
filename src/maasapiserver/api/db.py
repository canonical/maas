from contextlib import asynccontextmanager
from typing import AsyncIterator, Awaitable, Callable

from fastapi import Request, Response
from sqlalchemy.ext.asyncio import AsyncConnection
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..db import Database


class TransactionMiddleware(BaseHTTPMiddleware):
    """Run a request in a transaction, handling commit/rollback.

    This makes the database connection available as `request.state.conn`.
    """

    def __init__(self, app: ASGIApp, db: Database):
        super().__init__(app)
        self.db = db

    @asynccontextmanager
    async def get_connection(self) -> AsyncIterator[AsyncConnection]:
        """Return the connection in a transaction context manager."""
        async with self.db.engine.connect() as conn:
            async with conn.begin():
                yield conn

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        async with self.get_connection() as conn:
            request.state.conn = conn
            response = await call_next(request)
        return response


async def db_conn(request: Request) -> AsyncIterator[AsyncConnection]:
    """Context manager to run a section with a DB connection."""
    yield request.state.conn
