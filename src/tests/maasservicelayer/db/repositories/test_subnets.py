# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.db.repositories.subnets import SubnetsRepository
from maasservicelayer.models.subnets import Subnet
from tests.fixtures.factories.staticipaddress import (
    create_test_staticipaddress_entry,
)
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestSubnetsRepository(RepositoryCommonTests[Subnet]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> SubnetsRepository:
        return SubnetsRepository(db_connection)

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[Subnet]:
        created_subnets = [
            Subnet(
                **(
                    await create_test_subnet_entry(
                        fixture, name=str(i), description=str(i)
                    )
                )
            )
            for i in range(num_objects)
        ]
        return created_subnets

    @pytest.fixture
    async def _created_instance(self, fixture: Fixture) -> Subnet:
        return Subnet(
            **(
                await create_test_subnet_entry(
                    fixture, name="name", description="description"
                )
            )
        )


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestSubnetsRepositoryMethods:
    async def test_find_best_subnet_for_ip(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        await create_test_subnet_entry(fixture, cidr="10.0.0.0/16")
        subnet2 = await create_test_subnet_entry(fixture, cidr="10.0.1.0/24")

        ip = await create_test_staticipaddress_entry(fixture, ip="10.0.1.2")

        subnets = SubnetsRepository(db_connection)

        result = await subnets.find_best_subnet_for_ip(str(ip[0]["ip"]))

        assert result.id == subnet2["id"]
