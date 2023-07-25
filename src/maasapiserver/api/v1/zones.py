from fastapi import Depends

from .. import services
from ...api.auth import authenticated_user
from ...models.v1.entities.user import User
from ...models.v1.entities.zone import Zone
from ...services import ServiceCollectionV1
from ..base import Handler, handler


class ZoneHandler(Handler):
    """Handler for availability zones."""

    @handler(path="/zones", methods=["GET"])
    async def list(
        self,
        services: ServiceCollectionV1 = Depends(services),
        user: User = Depends(authenticated_user),
    ) -> list[Zone]:
        return await services.zones.list()
