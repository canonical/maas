# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.reservedips import ReservedIPsRepository
from maasservicelayer.models.reservedips import ReservedIP
from tests.fixtures.factories.reserved_ips import create_test_reserved_ip_entry
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestReservedIPsRepository(RepositoryCommonTests[ReservedIP]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> ReservedIPsRepository:
        return ReservedIPsRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[ReservedIP]:
        subnet = await create_test_subnet_entry(fixture)
        created_reserved_ips = [
            ReservedIP(
                **(
                    await create_test_reserved_ip_entry(
                        fixture,
                        subnet=subnet,
                        mac_address=f"01:02:03:04:05:{str(i).zfill(2)}",
                    )
                )
            )
            for i in range(num_objects)
        ]
        return created_reserved_ips

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> ReservedIP:
        subnet = await create_test_subnet_entry(fixture)
        return ReservedIP(
            **(await create_test_reserved_ip_entry(fixture, subnet=subnet))
        )

    @pytest.fixture
    async def instance_builder(self, *args, **kwargs):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_create(self, repository_instance, instance_builder):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_create_duplicated(
        self, repository_instance, instance_builder
    ):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_update(self, repository_instance, instance_builder):
        pass
