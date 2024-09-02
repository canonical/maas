# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.db.repositories.vlans import VlansRepository
from maasservicelayer.models.vlans import Vlan
from tests.fixtures.factories.fabric import create_test_fabric_entry
from tests.fixtures.factories.vlan import create_test_vlan_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestVlansRepository(RepositoryCommonTests[Vlan]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> VlansRepository:
        return VlansRepository(db_connection)

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[Vlan]:
        fabric = await create_test_fabric_entry(fixture)
        created_vlans = [
            Vlan(
                **(await create_test_vlan_entry(fixture, fabric_id=fabric.id))
            )
            for _ in range(num_objects)
        ]
        return created_vlans

    @pytest.fixture
    async def _created_instance(self, fixture: Fixture) -> Vlan:
        fabric = await create_test_fabric_entry(fixture)
        return Vlan(
            **(await create_test_vlan_entry(fixture, fabric_id=fabric.id))
        )
