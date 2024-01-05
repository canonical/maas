from contextlib import asynccontextmanager
import time
from typing import Any, AsyncIterator, Awaitable, Callable

from fastapi import Request, Response
from sqlalchemy import event
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


class DatabaseMetricsMiddleware(BaseHTTPMiddleware):
    """Track database-related metrics.

    It requires the database connection to be available as
    `request.state.conn`.
    """

    def __init__(self, app: ASGIApp, db: Database):
        super().__init__(app)
        self.db = db

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        query_metrics = {"latency": 0.0, "count": 0}
        request.state.query_metrics = query_metrics

        def before(*args: Any) -> None:
            request.state.cur_query_start = time.perf_counter()

        def after(*args: Any) -> None:
            request.state.query_metrics["latency"] += (
                time.perf_counter() - request.state.cur_query_start
            )
            request.state.query_metrics["count"] += 1
            del request.state.cur_query_start

        conn = request.state.conn.sync_connection
        event.listen(conn, "before_cursor_execute", before)
        event.listen(conn, "after_cursor_execute", after)
        try:
            response = await call_next(request)
        finally:
            event.remove(conn, "before_cursor_execute", before)
            event.remove(conn, "after_cursor_execute", after)
        return response
