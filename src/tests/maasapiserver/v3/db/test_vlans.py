# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v3.db.vlans import VlansRepository
from maasapiserver.v3.models.vlans import Vlan
from tests.fixtures.factories.fabric import create_test_fabric_entry
from tests.fixtures.factories.vlan import create_test_vlan_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasapiserver.v3.db.base import RepositoryCommonTests


class TestVlansRepository(RepositoryCommonTests[Vlan]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> VlansRepository:
        return VlansRepository(db_connection)

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture
    ) -> tuple[list[Vlan], int]:
        fabric = await create_test_fabric_entry(fixture)
        vlans_count = 10
        created_vlans = [
            Vlan(
                **(await create_test_vlan_entry(fixture, fabric_id=fabric.id))
            )
            for i in range(vlans_count)
        ][::-1]
        return created_vlans, vlans_count
