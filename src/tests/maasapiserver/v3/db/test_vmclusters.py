import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.operators import eq

from maasapiserver.common.db.tables import VmClusterTable, ZoneTable
from maasapiserver.v3.constants import DEFAULT_ZONE_NAME
from maasapiserver.v3.db.vmcluster import VmClustersRepository
from maasapiserver.v3.models.zones import Zone
from tests.fixtures.factories.vmcluster import create_test_vmcluster
from tests.fixtures.factories.zone import create_test_zone
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestVmClustersRepository:
    async def test_move_to_zone(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        [default_zone] = await fixture.get_typed(
            ZoneTable.name, Zone, eq(ZoneTable.c.name, DEFAULT_ZONE_NAME)
        )

        zone_a = await create_test_zone(fixture, name="A")
        zone_b = await create_test_zone(fixture, name="B")

        vmcluster_a = await create_test_vmcluster(
            fixture, name="A", zone_id=zone_a.id
        )
        vmcluster_b = await create_test_vmcluster(
            fixture, name="B", zone_id=zone_b.id
        )
        vmcluster_repository = VmClustersRepository(db_connection)
        await vmcluster_repository.move_to_zone(zone_b.id, zone_a.id)

        [updated_vmcluster_b] = await fixture.get(
            VmClusterTable.name, eq(VmClusterTable.c.id, vmcluster_b.id)
        )
        assert updated_vmcluster_b["zone_id"] == zone_a.id

        await vmcluster_repository.move_to_zone(zone_a.id, default_zone.id)
        [updated_vmcluster_a] = await fixture.get(
            VmClusterTable.name, eq(VmClusterTable.c.id, vmcluster_a.id)
        )
        [updated_vmcluster_b] = await fixture.get(
            VmClusterTable.name, eq(VmClusterTable.c.id, vmcluster_b.id)
        )
        assert updated_vmcluster_a["zone_id"] == default_zone.id
        assert updated_vmcluster_b["zone_id"] == default_zone.id
