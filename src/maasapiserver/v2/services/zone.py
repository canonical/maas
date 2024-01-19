from sqlalchemy import func, select

from maasapiserver.common.db.tables import NodeTable, ZoneTable
from maasapiserver.common.services._base import Service
from maasapiserver.v2.models.entities.zone import Zone
from maasserver.enum import NODE_TYPE


class ZoneService(Service):
    async def list(self) -> list[Zone]:
        stmt = (
            select(
                ZoneTable.c.id,
                ZoneTable.c.created,
                ZoneTable.c.updated,
                ZoneTable.c.name,
                ZoneTable.c.description,
                func.count()
                .filter(NodeTable.c.node_type == NODE_TYPE.DEVICE)
                .label("devices_count"),
                func.count()
                .filter(NodeTable.c.node_type == NODE_TYPE.MACHINE)
                .label("machines_count"),
                func.count()
                .filter(
                    NodeTable.c.node_type.in_(
                        [
                            NODE_TYPE.RACK_CONTROLLER,
                            NODE_TYPE.REGION_CONTROLLER,
                            NODE_TYPE.REGION_AND_RACK_CONTROLLER,
                        ]
                    )
                )
                .label("controllers_count"),
            )
            .select_from(
                ZoneTable.join(
                    NodeTable,
                    NodeTable.c.zone_id == ZoneTable.c.id,
                    isouter=True,
                )
            )
            .group_by(ZoneTable.c.id)
        )

        result = await self.conn.execute(stmt)
        return [Zone(**row._asdict()) for row in result.all()]
