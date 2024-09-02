import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.operators import eq

from maasapiserver.v3.constants import DEFAULT_ZONE_NAME
from maasapiserver.v3.db.bmc import BmcRepository
from maasservicelayer.db.tables import BMCTable, ZoneTable
from maasservicelayer.models.zones import Zone
from tests.fixtures.factories.bmc import create_test_bmc
from tests.fixtures.factories.zone import create_test_zone
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestBmcRepository:
    async def test_move_to_zone(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        [default_zone] = await fixture.get_typed(
            ZoneTable.name, Zone, eq(ZoneTable.c.name, DEFAULT_ZONE_NAME)
        )

        zone_a = await create_test_zone(fixture, name="A")
        zone_b = await create_test_zone(fixture, name="B")

        bmc_a = await create_test_bmc(
            fixture, zone_id=zone_a.id, power_parameters={"a": "a"}
        )
        bmc_b = await create_test_bmc(
            fixture, zone_id=zone_b.id, power_parameters={"b": "b"}
        )
        bmc_repository = BmcRepository(db_connection)
        await bmc_repository.move_to_zone(zone_b.id, zone_a.id)

        [updated_bmc_b] = await fixture.get(
            BMCTable.name, eq(BMCTable.c.id, bmc_b.id)
        )
        assert updated_bmc_b["zone_id"] == zone_a.id

        await bmc_repository.move_to_zone(zone_a.id, default_zone.id)
        [updated_bmc_a] = await fixture.get(
            BMCTable.name, eq(BMCTable.c.id, bmc_a.id)
        )
        [updated_bmc_b] = await fixture.get(
            BMCTable.name, eq(BMCTable.c.id, bmc_b.id)
        )
        assert updated_bmc_a["zone_id"] == default_zone.id
        assert updated_bmc_b["zone_id"] == default_zone.id
