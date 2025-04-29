#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.neighbours import NeighbourBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.neighbours import (
    NeighbourClauseFactory,
    NeighboursRepository,
)
from maasservicelayer.models.fields import MacAddress
from maasservicelayer.models.neighbours import Neighbour
from tests.fixtures.factories.discoveries import (
    create_test_rack_controller_entry,
)
from tests.fixtures.factories.interface import create_test_interface_entry
from tests.fixtures.factories.neighbours import create_test_neighbour_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestNeighbourClauseFactory:
    def test_with_ip(self) -> None:
        clause = NeighbourClauseFactory.with_ip(IPv4Address("10.0.0.1"))
        # We can't compile the statement with literal binds because they don't
        # exist for INET
        assert (
            str(clause.condition.compile())
            == "maasserver_neighbour.ip = :ip_1"
        )

    def test_with_mac(self) -> None:
        clause = NeighbourClauseFactory.with_mac(
            MacAddress("aa:bb:cc:dd:ee:ff")
        )
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_neighbour.mac_address = 'aa:bb:cc:dd:ee:ff'"
        )


class TestNeighboursRepository(RepositoryCommonTests[Neighbour]):
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
