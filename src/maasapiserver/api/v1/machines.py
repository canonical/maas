from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncConnection

from ...api.db import db_conn
from ...models.v1.entities.user import User
from ...models.v1.requests.machine import MachineListRequest
from ...models.v1.responses.machine import MachineListResponse
from ...services.v1.machine import MachineService
from ..auth import authenticated_user
from ..base import Handler, handler


class MachineHandler(Handler):
    @handler(path="/machines", methods=["POST"])
    async def list(
        self,
        request: MachineListRequest,
        connection: AsyncConnection = Depends(db_conn),
        user: User = Depends(authenticated_user),
    ) -> MachineListResponse:
        service = MachineService(connection)
        return await service.list(request)
