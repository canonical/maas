from contextlib import asynccontextmanager
import time
from typing import Any, AsyncIterator, Awaitable, Callable

from fastapi import Request, Response
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncConnection
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import structlog

from maasservicelayer.db import Database

logger = structlog.get_logger()


class TransactionMiddleware(BaseHTTPMiddleware):
    """Run a request in a transaction, handling commit/rollback.

    This makes the database connection available as `request.state.context.get_connection()`.
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
            request.state.context.set_connection(conn)
            response = await call_next(request)

        # TODO: rewrite the temporal service in order to just register the post commit hooks with no additional logic
        # After the transaction has been committed, we execute all the post commit hooks in the order they were registered.
        # for post_commit_hook in request.state.context.get_post_commit_hooks():
        #     try:
        #         await post_commit_hook()
        #     except Exception as e:
        #         logger.error("The transaction has been committed but a post commit hook has failed.", exc_info=e)
        #         raise e

        if hasattr(request.state, "services") and hasattr(
            request.state.services, "temporal"
        ):
            await request.state.services.temporal.post_commit()

        return response


class DatabaseMetricsMiddleware(BaseHTTPMiddleware):
    """Track database-related metrics.

    It requires the database connection to be available as
    `request.state.context.get_connection()`.
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

        conn = request.state.context.get_connection().sync_connection
        event.listen(conn, "before_cursor_execute", before)
        event.listen(conn, "after_cursor_execute", after)
        try:
            response = await call_next(request)
        finally:
            event.remove(conn, "before_cursor_execute", before)
            event.remove(conn, "after_cursor_execute", after)
        return response
