#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v3.constants import DEFAULT_ZONE_NAME
from maasservicelayer.builders.zones import ZoneBuilder
from maasservicelayer.context import Context
from maasservicelayer.db._debug import CompiledQuery
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.zones import (
    ZonesClauseFactory,
    ZonesRepository,
)
from maasservicelayer.db.tables import ZoneTable
from maasservicelayer.models.zones import Zone
from tests.fixtures.factories.node import (
    create_test_device_entry,
    create_test_machine_entry,
    create_test_rack_controller_entry,
)
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

    async def test_list_with_summary(
        self, repository_instance: ZonesRepository, fixture: Fixture
    ) -> None:
        zone = await repository_instance.get_default_zone()

        # 2 machines
        [
            await create_test_machine_entry(fixture, zone_id=zone.id)
            for _ in range(2)
        ]

        # 1 device
        await create_test_device_entry(fixture, zone_id=zone.id)

        # 3 controllers
        [
            await create_test_rack_controller_entry(fixture, zone_id=zone.id)
            for _ in range(3)
        ]

        zones = await repository_instance.list_with_summary(1, 20)
        assert len(zones.items) == 1
        assert zones.total == 1
        assert zones.items[0].machines_count == 2
        assert zones.items[0].devices_count == 1
        assert zones.items[0].controllers_count == 3

    async def test_list_with_summary_pagination(
        self, repository_instance: ZonesRepository, fixture: Fixture
    ) -> None:
        zone_names = [str(x) for x in range(4)]
        [
            await create_test_zone(fixture=fixture, name=name)
            for name in zone_names
        ]

        all_zones = []
        zones = await repository_instance.list_with_summary(1, 2)
        all_zones += zones.items
        assert len(zones.items) == 2
        assert zones.total == 5  # 4 just created + the default zone

        zones = await repository_instance.list_with_summary(2, 2)
        all_zones += zones.items
        assert len(zones.items) == 2
        assert zones.total == 5

        zones = await repository_instance.list_with_summary(3, 2)
        all_zones += zones.items
        assert len(zones.items) == 1
        assert zones.total == 5

        # Oldest records first
        expected_zone_order = (["default"] + zone_names)[::-1]
        for zone, name in zip(all_zones, expected_zone_order):
            assert zone.name == name
            assert zone.machines_count == 0
            assert zone.devices_count == 0
            assert zone.controllers_count == 0

    async def test_get_default_zone(
        self, repository_instance: ZonesRepository
    ) -> None:
        default_zone = await repository_instance.get_default_zone()
        assert default_zone.name == DEFAULT_ZONE_NAME
