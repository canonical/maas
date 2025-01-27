#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v3.constants import DEFAULT_ZONE_NAME
from maasservicelayer.context import Context
from maasservicelayer.db._debug import CompiledQuery
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.zones import (
    ZonesClauseFactory,
    ZonesRepository,
)
from maasservicelayer.db.tables import ZoneTable
from maasservicelayer.models.zones import Zone, ZoneBuilder
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


class TestZonesRepository(RepositoryCommonTests[Zone]):
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
    async def created_instance(self, fixture: Fixture) -> Zone:
        return await create_test_zone(
            fixture, name="myzone", description="description"
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[ZoneBuilder]:
        return ZoneBuilder

    @pytest.fixture
    async def instance_builder(self) -> ZoneBuilder:
        return ZoneBuilder(name="name", description="description")

    async def test_list_with_filters(
        self, repository_instance: ZonesRepository, created_instance: Zone
    ) -> None:
        query = QuerySpec(where=ZonesClauseFactory.with_ids([1]))
        zones = await repository_instance.list(1, 20, query)
        assert len(zones.items) == 1
        assert zones.total == 1
        assert zones.items[0].id == 1

        query = QuerySpec(
            where=ZonesClauseFactory.with_ids([1, created_instance.id])
        )
        zones = await repository_instance.list(1, 20, query)
        assert len(zones.items) == 2
        assert zones.total == 2

    async def test_get_default_zone(
        self, repository_instance: ZonesRepository
    ) -> None:
        default_zone = await repository_instance.get_default_zone()
        assert default_zone.name == DEFAULT_ZONE_NAME
