from fastapi import Depends

from .. import services
from ....common.api.base import Handler, handler
from ...models.entities.user import User
from ...models.requests.machine import MachineListRequest
from ...models.responses.machine import MachineListResponse
from ...services import ServiceCollectionV2
from ..auth import authenticated_user


class MachineHandler(Handler):
    @handler(path="/machines", methods=["POST"])
    async def list(
        self,
        request: MachineListRequest,
        services: ServiceCollectionV2 = Depends(services),
        user: User = Depends(authenticated_user),
    ) -> MachineListResponse:
        return await services.machines.list(request)
