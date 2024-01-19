from fastapi import Depends

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.v2.api import services
from maasapiserver.v2.api.auth import authenticated_user
from maasapiserver.v2.models.entities.user import User
from maasapiserver.v2.models.requests.machine import MachineListRequest
from maasapiserver.v2.models.responses.machine import MachineListResponse
from maasapiserver.v2.services import ServiceCollectionV2


class MachineHandler(Handler):
    @handler(path="/machines", methods=["POST"], include_in_schema=False)
    async def list(
        self,
        request: MachineListRequest,
        services: ServiceCollectionV2 = Depends(services),
        user: User = Depends(authenticated_user),
    ) -> MachineListResponse:
        return await services.machines.list(request)
