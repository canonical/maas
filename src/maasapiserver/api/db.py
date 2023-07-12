from typing import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncConnection


async def db_conn(request: Request) -> AsyncIterator[AsyncConnection]:
    """Context manager to run run a section with a DB connection."""
    engine = request.app.state.db.engine
    async with engine.connect() as conn:
        async with conn.begin():
            yield conn
