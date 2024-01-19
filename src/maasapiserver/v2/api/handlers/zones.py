from fastapi import Depends

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.v2.api import services
from maasapiserver.v2.api.auth import authenticated_user
from maasapiserver.v2.models.entities.user import User
from maasapiserver.v2.models.entities.zone import Zone
from maasapiserver.v2.services import ServiceCollectionV2


class ZoneHandler(Handler):
    """Handler for availability zones."""

    @handler(path="/zones", methods=["GET"], include_in_schema=False)
    async def list(
        self,
        services: ServiceCollectionV2 = Depends(services),
        user: User = Depends(authenticated_user),
    ) -> list[Zone]:
        return await services.zones.list()
