# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.ui_subnets import UISubnetsRepository
from maasservicelayer.models.ui_subnets import UISubnet
from maasservicelayer.models.vlans import Vlan
from tests.fixtures.factories.spaces import create_test_space_entry
from tests.fixtures.factories.subnet import create_test_ui_subnet_entry
from tests.fixtures.factories.vlan import create_test_vlan_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import (
    ReadOnlyRepositoryCommonTests,
)


class TestUISubnetsRepository(ReadOnlyRepositoryCommonTests[UISubnet]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> UISubnetsRepository:
        return UISubnetsRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[UISubnet]:
        space = await create_test_space_entry(fixture)
        vlan = Vlan(**await create_test_vlan_entry(fixture, space_id=space.id))
        created_ui_subnets = [
            await create_test_ui_subnet_entry(
                fixture, space=space, vlan=vlan, cidr=f"10.0.0.{i}"
            )
            for i in range(num_objects)
        ]
        return created_ui_subnets

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> UISubnet:
        return await create_test_ui_subnet_entry(fixture, cidr="10.0.0.1")
