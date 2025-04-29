# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.mdns import MDNSBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.mdns import MDNSRepository
from maasservicelayer.models.mdns import MDNS
from tests.fixtures.factories.interface import create_test_interface_entry
from tests.fixtures.factories.mdns import create_test_mdns_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestMDNSRepository(RepositoryCommonTests[MDNS]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> MDNSRepository:
        return MDNSRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[MDNS]:
        interface = await create_test_interface_entry(fixture)
        return [
            await create_test_mdns_entry(
                fixture,
                hostname="foo",
                ip=f"10.0.0.{i + 1}",
                interface_id=interface.id,
            )
            for i in range(num_objects)
        ]

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> MDNS:
        interface = await create_test_interface_entry(fixture)
        return await create_test_mdns_entry(
            fixture, hostname="foo", ip="10.0.0.1", interface_id=interface.id
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[MDNSBuilder]:
        return MDNSBuilder

    @pytest.fixture
    async def instance_builder(self) -> MDNSBuilder:
        return MDNSBuilder(
            hostname="bar", ip="10.0.0.200", count=1, interface_id=5
        )

    @pytest.mark.skip(reason="Not applicable")
    async def test_create_duplicated(
        self, repository_instance, instance_builder
    ):
        raise NotImplementedError()
