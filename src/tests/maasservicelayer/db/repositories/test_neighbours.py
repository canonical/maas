#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import ip_address

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.neighbours import NeighbourBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.neighbours import NeighboursRepository
from maasservicelayer.filters.neighbours import NeighbourFilters
from maasservicelayer.filters.query import QuerySpec
from maasservicelayer.models.fields import MacAddress
from maasservicelayer.models.neighbours import Neighbour
from tests.fixtures.factories.discoveries import (
    create_test_rack_controller_entry,
)
from tests.fixtures.factories.interface import create_test_interface_entry
from tests.fixtures.factories.neighbours import create_test_neighbour_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestNeighboursRepository(RepositoryCommonTests[Neighbour]):
    @pytest.mark.parametrize("ip", ["10.0.0.1", "2001:db8::1"])
    async def test_get_by_ip_and_mac(
        self,
        repository_instance: NeighboursRepository,
        fixture: Fixture,
        ip: str,
    ) -> None:
        rack_controller = await create_test_rack_controller_entry(fixture)
        interface = await create_test_interface_entry(
            fixture, node=rack_controller
        )
        expected = await create_test_neighbour_entry(
            fixture,
            interface_id=interface.id,
            ip=ip,
            mac_address="aa:bb:cc:dd:ee:ff",
        )
        await create_test_neighbour_entry(
            fixture,
            interface_id=interface.id,
            ip="10.0.0.2",
            mac_address="00:11:22:33:44:55",
        )

        for filter in (
            NeighbourFilters.with_ip(ip_address(ip)),
            NeighbourFilters.with_mac(MacAddress("aa:bb:cc:dd:ee:ff")),
        ):
            result = await repository_instance.get_many(
                QuerySpec(where=filter)
            )
            assert result == [expected]

    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> NeighboursRepository:
        return NeighboursRepository(context=Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[Neighbour]:
        rack_controller = await create_test_rack_controller_entry(fixture)
        interface = await create_test_interface_entry(
            fixture, node=rack_controller
        )

        return [
            await create_test_neighbour_entry(
                fixture, interface_id=interface.id
            )
            for _ in range(num_objects)
        ]

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> Neighbour:
        rack_controller = await create_test_rack_controller_entry(fixture)
        interface = await create_test_interface_entry(
            fixture, node=rack_controller
        )
        return await create_test_neighbour_entry(
            fixture, interface_id=interface.id
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[NeighbourBuilder]:
        return NeighbourBuilder

    @pytest.fixture
    async def instance_builder(self, *args, **kwargs) -> NeighbourBuilder:
        return NeighbourBuilder(
            ip="10.0.0.1",
            mac_address="00:00:00:00:00:00",
            time=1,
            count=1,
            interface_id=2,
        )

    @pytest.mark.skip(reason="Not applicable")
    async def test_create_duplicated(
        self, repository_instance, instance_builder
    ):
        raise NotImplementedError()

    @pytest.mark.skip(reason="Not applicable")
    async def test_create_many_duplicated(
        self, repository_instance, instance_builder
    ):
        raise NotImplementedError()
