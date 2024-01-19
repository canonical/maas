from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.api.db import db_conn
from maasapiserver.v2.services import ServiceCollectionV2


def services(
    db_conn: AsyncConnection = Depends(db_conn),
) -> ServiceCollectionV2:
    """Dependency to return the services collection."""
    return ServiceCollectionV2(db_conn)
