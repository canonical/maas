from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncConnection

from ..services import ServiceCollectionV1
from .db import db_conn


def services(
    db_conn: AsyncConnection = Depends(db_conn),
) -> ServiceCollectionV1:
    """Dependency to return the services collection."""
    return ServiceCollectionV1(db_conn)
