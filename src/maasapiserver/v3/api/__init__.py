from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.api.db import db_conn
from maasapiserver.v3.services import ServiceCollectionV3


def services(
    db_conn: AsyncConnection = Depends(db_conn),
) -> ServiceCollectionV3:
    """Dependency to return the services collection."""
    return ServiceCollectionV3(db_conn)
