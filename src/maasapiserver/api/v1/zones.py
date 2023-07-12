from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncConnection

from ...api.auth import authenticated_user
from ...api.db import db_conn
from ...models.v1.entities.user import User
from ...models.v1.entities.zone import Zone
from ...services.v1.zone import ZoneService
from ..base import Handler, handler


class ZoneHandler(Handler):
    """Handler for availability zones."""

    @handler(path="/zones", methods=["GET"])
    async def list(
        self,
        connection: AsyncConnection = Depends(db_conn),
        user: User = Depends(authenticated_user),
    ) -> list[Zone]:
        service = ZoneService(connection)
        return await service.list()
