# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v3.db.subnets import SubnetsRepository
from maasapiserver.v3.models.subnets import Subnet
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasapiserver.v3.db.base import RepositoryCommonTests


class TestSubnetsRepository(RepositoryCommonTests[Subnet]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> SubnetsRepository:
        return SubnetsRepository(db_connection)

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture
    ) -> tuple[list[Subnet], int]:
        subnets_count = 10
        created_subnets = [
            Subnet(
                **(
                    await create_test_subnet_entry(
                        fixture, name=str(i), description=str(i)
                    )
                )
            )
            for i in range(subnets_count)
        ][::-1]
        return created_subnets, subnets_count

    @pytest.fixture
    async def _created_instance(self, fixture: Fixture) -> Subnet:
        return Subnet(
            **(
                await create_test_subnet_entry(
                    fixture, name="name", description="description"
                )
            )
        )

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_find_by_id_not_found(
        self, repository_instance: SubnetsRepository
    ):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_find_by_id(
        self,
        repository_instance: SubnetsRepository,
        _created_instance: Subnet,
    ):
        pass
