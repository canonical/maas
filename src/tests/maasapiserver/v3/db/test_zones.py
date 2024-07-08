from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.operators import eq

from maasapiserver.common.db.tables import ZoneTable
from maasapiserver.common.models.exceptions import AlreadyExistsException
from maasapiserver.v3.api.models.requests.zones import ZoneRequest
from maasapiserver.v3.constants import DEFAULT_ZONE_NAME
from maasapiserver.v3.db.zones import ZonesRepository
from maasapiserver.v3.models.zones import Zone
from tests.fixtures.factories.zone import create_test_zone
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasapiserver.v3.db.base import RepositoryCommonTests


class TestZonesRepo(RepositoryCommonTests[Zone]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> ZonesRepository:
        return ZonesRepository(db_connection)

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture
    ) -> tuple[list[Zone], int]:
        zones_count = 10
        # The "default" zone with id=1 is created at startup with the migrations.
        # By consequence, we create zones_size-1 zones here.
        created_zones = [
            (await create_test_zone(fixture, name=str(i), description=str(i)))
            for i in range(0, zones_count - 1)
        ][::-1]
        return created_zones, zones_count

    @pytest.fixture
    async def _created_instance(self, fixture: Fixture) -> Zone:
        return await create_test_zone(
            fixture, name="myzone", description="description"
        )


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestZonesRepository:
    async def test_create(self, db_connection: AsyncConnection) -> None:
        now = datetime.utcnow()
        zones_repository = ZonesRepository(db_connection)
        created_zone = await zones_repository.create(
            ZoneRequest(name="my_zone", description="my description")
        )
        assert created_zone.id > 1
        assert created_zone.name == "my_zone"
        assert created_zone.description == "my description"
        assert created_zone.created.astimezone(timezone.utc) >= now.astimezone(
            timezone.utc
        )
        assert created_zone.updated.astimezone(timezone.utc) >= now.astimezone(
            timezone.utc
        )

    async def test_create_duplicated(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        zones_repository = ZonesRepository(db_connection)
        created_zone = await create_test_zone(fixture)

        with pytest.raises(AlreadyExistsException):
            await zones_repository.create(
                ZoneRequest(
                    name=created_zone.name,
                    description=created_zone.description,
                )
            )

    async def test_delete(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        zones_repository = ZonesRepository(db_connection)
        created_zone = await create_test_zone(fixture)
        assert (await zones_repository.delete(created_zone.id)) is None

        zones = await fixture.get(
            ZoneTable.name, eq(ZoneTable.c.id, created_zone.id)
        )
        assert zones == []

        # If the entity does not exist, silently ignore it.
        assert (await zones_repository.delete(created_zone.id)) is None

    async def test_get_default_zone(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        zones_repository = ZonesRepository(db_connection)
        default_zone = await zones_repository.get_default_zone()
        assert default_zone.name == DEFAULT_ZONE_NAME
