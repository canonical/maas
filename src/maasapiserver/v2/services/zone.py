from sqlalchemy import func, select

from maasapiserver.v2.models.entities.zone import Zone
from maascommon.enums.node import NodeTypeEnum
from maasservicelayer.db.tables import NodeTable, ZoneTable
from maasservicelayer.services.base import Service


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
                .filter(NodeTable.c.node_type == NodeTypeEnum.DEVICE)
                .label("devices_count"),
                func.count()
                .filter(NodeTable.c.node_type == NodeTypeEnum.MACHINE)
                .label("machines_count"),
                func.count()
                .filter(
                    NodeTable.c.node_type.in_(
                        [
                            NodeTypeEnum.RACK_CONTROLLER,
                            NodeTypeEnum.REGION_CONTROLLER,
                            NodeTypeEnum.REGION_AND_RACK_CONTROLLER,
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
            .order_by(ZoneTable.c.id)
        )

        result = await self.context.get_connection().execute(stmt)
        return [Zone(**row._asdict()) for row in result.all()]
