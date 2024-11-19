#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.operators import eq

from maasapiserver.v3.constants import DEFAULT_ZONE_NAME
from maasservicelayer.context import Context
from maasservicelayer.db._debug import CompiledQuery
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.zones import (
    ZoneResourceBuilder,
    ZonesClauseFactory,
    ZonesRepository,
)
from maasservicelayer.db.tables import ZoneTable
from maasservicelayer.exceptions.catalog import AlreadyExistsException
from maasservicelayer.models.zones import Zone
from maasservicelayer.utils.date import utcnow
from tests.fixtures.factories.zone import create_test_zone
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestZonesClauseFactory:
    def test_factory(self):
        clause = ZonesClauseFactory.with_ids([1, 2])

        stmt = (
            select(ZoneTable.c.id)
            .select_from(ZoneTable)
            .where(clause.condition)
        )
        assert (
            str(CompiledQuery(stmt).sql)
            == "SELECT maasserver_zone.id \nFROM maasserver_zone \nWHERE maasserver_zone.id IN (__[POSTCOMPILE_id_1])"
        )
        assert CompiledQuery(stmt).params == {
            "id_1": [1, 2],
        }


class TestZoneCreateOrUpdateResourceBuilder:
    def test_builder(self) -> None:
        now = utcnow()
        resource = (
            ZoneResourceBuilder()
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
        return ZonesRepository(Context(connection=db_connection))

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

        zones_repository = ZonesRepository(Context(connection=db_connection))

        query = QuerySpec(where=ZonesClauseFactory.with_ids([1]))
        zones = await zones_repository.list(None, 20, query)
        assert len(zones.items) == 1
        assert zones.items[0].id == 1

        query = QuerySpec(
            where=ZonesClauseFactory.with_ids([1, created_zone.id])
        )
        zones = await zones_repository.list(None, 20, query)
        assert len(zones.items) == 2

    async def test_create(self, db_connection: AsyncConnection) -> None:
        now = utcnow()
        zones_repository = ZonesRepository(Context(connection=db_connection))
        created_zone = await zones_repository.create(
            ZoneResourceBuilder()
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
        zones_repository = ZonesRepository(Context(connection=db_connection))
        created_zone = await create_test_zone(fixture)

        with pytest.raises(AlreadyExistsException):
            await zones_repository.create(
                ZoneResourceBuilder()
                .with_name(created_zone.name)
                .with_description(created_zone.description)
                .with_created(now)
                .with_updated(now)
                .build()
            )

    async def test_delete(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        zones_repository = ZonesRepository(Context(connection=db_connection))
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
        zones_repository = ZonesRepository(Context(connection=db_connection))
        default_zone = await zones_repository.get_default_zone()
        assert default_zone.name == DEFAULT_ZONE_NAME
