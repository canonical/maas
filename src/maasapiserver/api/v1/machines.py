from fastapi import Depends

from .. import services
from ...models.v1.entities.user import User
from ...models.v1.requests.machine import MachineListRequest
from ...models.v1.responses.machine import MachineListResponse
from ...services import ServiceCollectionV1
from ..auth import authenticated_user
from ..base import Handler, handler


class MachineHandler(Handler):
    @handler(path="/machines", methods=["POST"])
    async def list(
        self,
        request: MachineListRequest,
        services: ServiceCollectionV1 = Depends(services),
        user: User = Depends(authenticated_user),
    ) -> MachineListResponse:
        return await services.machines.list(request)
