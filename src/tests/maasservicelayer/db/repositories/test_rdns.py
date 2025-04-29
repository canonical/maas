# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.rdns import RDNSBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.rdns import RDNSRepository
from maasservicelayer.models.rdns import RDNS
from tests.fixtures.factories.node import create_test_region_controller_entry
from tests.fixtures.factories.rdns import create_test_rdns_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestRDNSRepository(RepositoryCommonTests[RDNS]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> RDNSRepository:
        return RDNSRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[RDNS]:
        region = await create_test_region_controller_entry(fixture)
        return [
            await create_test_rdns_entry(
                fixture,
                hostname="foo",
                ip=f"10.0.0.{i + 1}",
                observer_id=region["id"],
            )
            for i in range(num_objects)
        ]

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> RDNS:
        region = await create_test_region_controller_entry(fixture)
        return await create_test_rdns_entry(
            fixture, hostname="foo", ip="10.0.0.1", observer_id=region["id"]
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[RDNSBuilder]:
        return RDNSBuilder

    @pytest.fixture
    async def instance_builder(self) -> RDNSBuilder:
        return RDNSBuilder(
            hostname="bar",
            ip="10.0.0.200",
            hostnames=["foo", "bar", "baz"],
            observer_id=5,
        )

    @pytest.mark.skip(reason="Not applicable")
    async def test_create_duplicated(
        self, repository_instance, instance_builder
    ):
        raise NotImplementedError()
