# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest
from sqlalchemy import and_
from sqlalchemy.sql.operators import eq

from maasservicelayer.builders.openfga_tuple import OpenFGATupleBuilder
from maasservicelayer.builders.resource_pools import ResourcePoolBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.resource_pools import (
    ResourcePoolClauseFactory,
    ResourcePoolRepository,
)
from maasservicelayer.db.tables import OpenFGATupleTable
from maasservicelayer.exceptions.catalog import BadRequestException
from maasservicelayer.models.base import MaasBaseModel
from maasservicelayer.models.resource_pools import ResourcePool
from maasservicelayer.services import (
    OpenFGATupleService,
    ResourcePoolsService,
    ServiceCollectionV3,
)
from maasservicelayer.services.base import BaseService
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestCommonResourcePoolsService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BaseService:
        return ResourcePoolsService(
            context=Context(),
            resource_pools_repository=Mock(ResourcePoolRepository),
            openfga_tuples_service=Mock(OpenFGATupleService),
        )

    @pytest.fixture
    def test_instance(self) -> MaasBaseModel:
        return ResourcePool(
            id=2,
            name="test",
            description="",
            created=utcnow(),
            updated=utcnow(),
        )


@pytest.mark.asyncio
class TestIntegrationResourcePoolsService:
    async def test_create_stores_openfga_tuple(
        self, fixture: Fixture, services: ServiceCollectionV3
    ):
        resource_pool = await services.resource_pools.create(
            ResourcePoolBuilder(name="test", description="")
        )
        retrieved_pool = await fixture.get(
            OpenFGATupleTable.fullname,
            and_(
                eq(OpenFGATupleTable.c.object_type, "pool"),
                eq(OpenFGATupleTable.c.object_id, str(resource_pool.id)),
                eq(OpenFGATupleTable.c.relation, "parent"),
            ),
        )
        assert len(retrieved_pool) == 1
        assert retrieved_pool[0]["_user"] == "maas:0"
        assert retrieved_pool[0]["object_type"] == "pool"
        assert retrieved_pool[0]["object_id"] == str(resource_pool.id)
        assert retrieved_pool[0]["relation"] == "parent"

    async def test_delete_removes_openfga_tuple(
        self, fixture: Fixture, services: ServiceCollectionV3
    ):
        resource_pool = await services.resource_pools.create(
            ResourcePoolBuilder(name="test", description="")
        )
        await services.resource_pools.delete_by_id(resource_pool.id)
        retrieved_pool = await fixture.get(
            OpenFGATupleTable.fullname,
            and_(
                eq(OpenFGATupleTable.c.object_type, "pool"),
                eq(OpenFGATupleTable.c.object_id, str(resource_pool.id)),
                eq(OpenFGATupleTable.c.relation, "parent"),
            ),
        )
        assert len(retrieved_pool) == 0

    async def test_delete_many_removes_openfga_tuples(
        self, fixture: Fixture, services: ServiceCollectionV3
    ):
        resource_pool_1 = await services.resource_pools.create(
            ResourcePoolBuilder(name="test1", description="")
        )
        resource_pool_2 = await services.resource_pools.create(
            ResourcePoolBuilder(name="test2", description="")
        )
        await services.resource_pools.delete_many(
            QuerySpec(
                where=ResourcePoolClauseFactory.with_ids(
                    [resource_pool_1.id, resource_pool_2.id]
                )
            )
        )
        retrieved_pools = await fixture.get(
            OpenFGATupleTable.fullname,
            and_(
                eq(OpenFGATupleTable.c.object_type, "pool"),
                eq(OpenFGATupleTable.c.relation, "parent"),
                OpenFGATupleTable.c.object_id.in_(
                    [str(resource_pool_1.id), str(resource_pool_2.id)]
                ),
            ),
        )
        assert len(retrieved_pools) == 0


@pytest.mark.asyncio
class TestResourcePoolsService:
    async def test_list_ids(self) -> None:
        resource_pool_repository_mock = Mock(ResourcePoolRepository)
        resource_pool_repository_mock.list_ids.return_value = {1, 2, 3}
        resource_pools_service = ResourcePoolsService(
            context=Context(),
            resource_pools_repository=resource_pool_repository_mock,
            openfga_tuples_service=Mock(OpenFGATupleService),
        )
        ids_list = await resource_pools_service.list_ids()
        resource_pool_repository_mock.list_ids.assert_called_once()
        assert ids_list == {1, 2, 3}

    async def test_cannot_delete_default_resourcepool(self) -> None:
        resource_pools_repository = Mock(ResourcePoolRepository)
        resource_pools_service = ResourcePoolsService(
            context=Context(),
            resource_pools_repository=resource_pools_repository,
            openfga_tuples_service=Mock(OpenFGATupleService),
        )
        resource_pool = ResourcePool(id=0, name="default", description="")
        with pytest.raises(BadRequestException):
            await resource_pools_service.pre_delete_hook(resource_pool)

    async def test_create_calls_post_create_hook(self) -> None:
        resource_pools_repository = Mock(ResourcePoolRepository)
        openfga_tuples_service = Mock(OpenFGATupleService)
        resource_pools_service = ResourcePoolsService(
            context=Context(),
            resource_pools_repository=resource_pools_repository,
            openfga_tuples_service=openfga_tuples_service,
        )
        resource_pool = ResourcePool(id=1, name="test", description="")
        await resource_pools_service.post_create_hook(resource_pool)
        openfga_tuples_service.create.assert_called_once()

    async def test_delete_calls_post_delete_hook(self) -> None:
        resource_pools_repository = Mock(ResourcePoolRepository)
        openfga_tuples_service = Mock(OpenFGATupleService)
        resource_pools_service = ResourcePoolsService(
            context=Context(),
            resource_pools_repository=resource_pools_repository,
            openfga_tuples_service=openfga_tuples_service,
        )
        resource_pool = ResourcePool(id=1, name="test", description="")
        await resource_pools_service.post_delete_hook(resource_pool)
        openfga_tuples_service.delete_pool.assert_called_once_with(1)

    async def test_create_many_calls_post_create_many_hook(self) -> None:
        resource_pools_repository = Mock(ResourcePoolRepository)
        openfga_tuples_service = Mock(OpenFGATupleService)
        resource_pools_service = ResourcePoolsService(
            context=Context(),
            resource_pools_repository=resource_pools_repository,
            openfga_tuples_service=openfga_tuples_service,
        )
        resource_pool_1 = ResourcePool(id=1, name="test1", description="")
        resource_pool_2 = ResourcePool(id=2, name="test2", description="")
        await resource_pools_service.post_create_many_hook(
            [resource_pool_1, resource_pool_2]
        )
        openfga_tuples_service.create.assert_any_call(
            OpenFGATupleBuilder.build_pool(str(resource_pool_1.id))
        )
        openfga_tuples_service.create.assert_any_call(
            OpenFGATupleBuilder.build_pool(str(resource_pool_2.id))
        )
