from sqlalchemy import update
from sqlalchemy.sql.operators import eq

from maasapiserver.common.db.tables import BMCTable
from maasapiserver.v3.api.models.requests.bmc import BmcRequest
from maasapiserver.v3.db.base import BaseRepository
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.bmc import Bmc


class BmcRepository(BaseRepository[Bmc, BmcRequest]):
    async def create(self, request: BmcRequest) -> Bmc:
        raise Exception("Not implemented yet.")

    async def find_by_id(self, id: int) -> Bmc | None:
        raise Exception("Not implemented yet.")

    async def list(self, token: str | None, size: int) -> ListResult[Bmc]:
        raise Exception("Not implemented yet.")

    async def update(self, resource: Bmc) -> Bmc:
        raise Exception("Not implemented yet.")

    async def delete(self, id: int) -> None:
        raise Exception("Not implemented yet.")

    async def move_to_zone(self, old_zone_id: int, new_zone_id: int) -> None:
        stmt = (
            update(BMCTable)
            .where(eq(BMCTable.c.zone_id, old_zone_id))
            .values(zone_id=new_zone_id)
        )
        await self.connection.execute(stmt)
