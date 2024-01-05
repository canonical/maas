from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncConnection


def db_conn(request: Request) -> AsyncConnection:
    """Dependency to return the database connection."""
    return request.state.conn
