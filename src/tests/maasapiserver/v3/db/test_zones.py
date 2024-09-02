from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.operators import eq

from maasapiserver.common.models.exceptions import AlreadyExistsException
from maasapiserver.common.utils.date import utcnow
from maasapiserver.v3.constants import DEFAULT_ZONE_NAME
from maasapiserver.v3.db.zones import (
    ZoneCreateOrUpdateResourceBuilder,
    ZonesFilterQueryBuilder,
    ZonesRepository,
)
from maasservicelayer.db.tables import ZoneTable
from maasservicelayer.models.zones import Zone
from tests.fixtures.factories.zone import create_test_zone
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasapiserver.v3.db.base import RepositoryCommonTests


class TestZoneCreateOrUpdateResourceBuilder:
    def test_builder(self) -> None:
        now = utcnow()
        resource = (
            ZoneCreateOrUpdateResourceBuilder()
            .with_name("test")
            .with_description("descr")
            .with_created(now)
            .with_updated(now)
            .build()
        )

        assert resource.get_values() == {
            "name": "test",
            "description": "descr",
            "created": now,
            "updated": now,
        }


class TestZonesRepo(RepositoryCommonTests[Zone]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> ZonesRepository:
        return ZonesRepository(db_connection)

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[Zone]:
        # The default zone is created by the migration and it has the following
        # timestamp hardcoded in the test sql dump,
        # see src/maasserver/testing/inital.maas_test.sql:12804
        ts = datetime(2021, 11, 19, 12, 40, 43, 705399, tzinfo=timezone.utc)
        created_zones = [
            Zone(
                id=1,
                name="default",
                description="",
                created=ts,
                updated=ts,
            )
        ]
        created_zones.extend(
            [
                (
                    await create_test_zone(
                        fixture, name=str(i), description=str(i)
                    )
                )
                for i in range(0, num_objects - 1)
            ]
        )
        return created_zones

    @pytest.fixture
    async def _created_instance(self, fixture: Fixture) -> Zone:
        return await create_test_zone(
            fixture, name="myzone", description="description"
        )


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestZonesRepository:
    async def test_list_with_filters(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        created_zone = await create_test_zone(fixture)

        zones_repository = ZonesRepository(db_connection)

        query = ZonesFilterQueryBuilder().with_ids([1]).build()
        zones = await zones_repository.list(None, 20, query)
        assert len(zones.items) == 1
        assert zones.items[0].id == 1

        query = (
            ZonesFilterQueryBuilder().with_ids([1, created_zone.id]).build()
        )
        zones = await zones_repository.list(None, 20, query)
        assert len(zones.items) == 2

    async def test_create(self, db_connection: AsyncConnection) -> None:
        now = utcnow()
        zones_repository = ZonesRepository(db_connection)
        created_zone = await zones_repository.create(
            ZoneCreateOrUpdateResourceBuilder()
            .with_name("my_zone")
            .with_description("my description")
            .with_created(now)
            .with_updated(now)
            .build()
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
        now = utcnow()
        zones_repository = ZonesRepository(db_connection)
        created_zone = await create_test_zone(fixture)

        with pytest.raises(AlreadyExistsException):
            await zones_repository.create(
                ZoneCreateOrUpdateResourceBuilder()
                .with_name(created_zone.name)
                .with_description(created_zone.description)
                .with_created(now)
                .with_updated(now)
                .build()
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
