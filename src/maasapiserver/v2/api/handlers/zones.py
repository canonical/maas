from fastapi import Depends

from .. import services
from ....common.api.base import Handler, handler
from ...models.entities.user import User
from ...models.entities.zone import Zone
from ...services import ServiceCollectionV2
from ..auth import authenticated_user


class ZoneHandler(Handler):
    """Handler for availability zones."""

    @handler(path="/zones", methods=["GET"])
    async def list(
        self,
        services: ServiceCollectionV2 = Depends(services),
        user: User = Depends(authenticated_user),
    ) -> list[Zone]:
        return await services.zones.list()
