from sqlalchemy import update
from sqlalchemy.sql.operators import eq

from maasapiserver.common.db.tables import NodeTable
from maasapiserver.v3.api.models.requests.nodes import NodeRequest
from maasapiserver.v3.api.models.requests.query import PaginationParams
from maasapiserver.v3.db.base import BaseRepository
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.nodes import Node


class NodesRepository(BaseRepository[Node, NodeRequest]):
    async def create(self, request: NodeRequest) -> Node:
        raise Exception("Not implemented yet.")

    async def find_by_id(self, id: int) -> Node | None:
        raise Exception("Not implemented yet.")

    async def list(
        self, pagination_params: PaginationParams
    ) -> ListResult[Node]:
        raise Exception("Not implemented yet.")

    async def update(self, id: int, request: NodeRequest) -> Node:
        raise Exception("Not implemented yet.")

    async def delete(self, id: int) -> None:
        raise Exception("Not implemented yet.")

    async def move_to_zone(self, old_zone_id: int, new_zone_id: int) -> None:
        stmt = (
            update(NodeTable)
            .where(eq(NodeTable.c.zone_id, old_zone_id))
            .values(zone_id=new_zone_id)
        )
        await self.connection.execute(stmt)
