#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type
from unittest.mock import Mock

import pytest
from sqlalchemy import Table

from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.exceptions.catalog import (
    NotFoundException,
    PreconditionFailedException,
)
from maasservicelayer.models.base import (
    ListResult,
    MaasBaseModel,
    make_builder,
    ResourceBuilder,
)
from maasservicelayer.services.base import BaseService


class DummyMaasBaseModel(MaasBaseModel):
    def etag(self) -> str:
        return "test"


DummyMaasBaseModelBuilder = make_builder(DummyMaasBaseModel)


class DummyRepository(BaseRepository[DummyMaasBaseModel]):
    def get_repository_table(self) -> Table:
        return Mock(Table)

    def get_model_factory(self) -> Type[DummyMaasBaseModel]:
        return DummyMaasBaseModel


class DummyService(
    BaseService[DummyMaasBaseModel, DummyRepository, DummyMaasBaseModelBuilder]
):
    def __init__(self, context: Context, repository: DummyRepository):
        super().__init__(context, repository)


@pytest.fixture()
def repository_mock():
    return Mock(DummyRepository)


@pytest.fixture()
def service(repository_mock):
    return DummyService(Context(), repository_mock)


@pytest.mark.asyncio
class TestBaseService:
    async def test_get_one(self, repository_mock, service):
        resource = DummyMaasBaseModel(id=0)
        repository_mock.get_one.return_value = resource
        query = QuerySpec()
        result = await service.get_one(query)

        repository_mock.get_one.assert_awaited_once_with(query=query)
        assert result == resource

    async def test_get_by_id(self, repository_mock, service):
        resource = DummyMaasBaseModel(id=0)
        repository_mock.get_by_id.return_value = resource
        result = await service.get_by_id(0)

        repository_mock.get_by_id.assert_awaited_once_with(id=0)
        assert result == resource

    async def test_get_many(self, repository_mock, service):
        resources = [DummyMaasBaseModel(id=0)]
        repository_mock.get_many.return_value = resources
        query = QuerySpec()
        results = await service.get_many(query)

        repository_mock.get_many.assert_awaited_once_with(query=query)
        assert results == resources

    async def test_create(self, repository_mock, service):
        resource = DummyMaasBaseModel(id=0)
        repository_mock.create.return_value = resource
        builder = ResourceBuilder()
        result = await service.create(builder)

        repository_mock.create.assert_awaited_once_with(builder=builder)
        assert result == resource

    async def test_list(self, repository_mock, service):
        resources = ListResult[DummyMaasBaseModel](
            items=[DummyMaasBaseModel(id=0)], total=1
        )
        repository_mock.list.return_value = resources
        query = QuerySpec()
        results = await service.list(1, 10, query)

        repository_mock.list.assert_awaited_once_with(
            page=1, size=10, query=query
        )
        assert results == resources

    async def test_update_one(self, repository_mock, service):
        resource = DummyMaasBaseModel(id=0)
        repository_mock.get_one.return_value = resource
        repository_mock.update_by_id.return_value = resource
        builder = ResourceBuilder()
        query = QuerySpec()
        result = await service.update_one(query, builder)
        repository_mock.get_one.assert_awaited_once_with(query=query)
        repository_mock.update_by_id.assert_awaited_once_with(
            id=0, builder=builder
        )
        assert result == resource

    async def test_update_one_not_found(self, repository_mock, service):
        resource = DummyMaasBaseModel(id=0)
        repository_mock.get_one.return_value = None
        repository_mock.update_by_id.return_value = resource
        builder = ResourceBuilder()
        query = QuerySpec()
        with pytest.raises(NotFoundException):
            await service.update_one(query, builder)

    async def test_update_one_etag_matches(self, repository_mock, service):
        resource = DummyMaasBaseModel(id=0)
        repository_mock.get_one.return_value = resource
        repository_mock.update_by_id.return_value = resource
        builder = ResourceBuilder()
        query = QuerySpec()
        result = await service.update_one(query, builder, "test")
        repository_mock.get_one.assert_awaited_once_with(query=query)
        repository_mock.update_by_id.assert_awaited_once_with(
            id=0, builder=builder
        )
        assert result == resource

    async def test_update_one_etag_not_matching(
        self, repository_mock, service
    ):
        resource = DummyMaasBaseModel(id=0)
        repository_mock.get_one.return_value = resource
        repository_mock.update_by_id.return_value = resource
        builder = ResourceBuilder()
        query = QuerySpec()
        with pytest.raises(PreconditionFailedException):
            await service.update_one(query, builder, "not a match")
        repository_mock.get_one.assert_awaited_once_with(query=query)
        repository_mock.update_by_id.assert_not_called()

    async def test_update_by_id(self, repository_mock, service):
        resource = DummyMaasBaseModel(id=0)
        repository_mock.get_by_id.return_value = resource
        repository_mock.update_by_id.return_value = resource
        builder = ResourceBuilder()
        result = await service.update_by_id(0, builder)
        repository_mock.get_by_id.assert_awaited_once_with(id=0)
        repository_mock.update_by_id.assert_awaited_once_with(
            id=0, builder=builder
        )
        assert result == resource

    async def test_update_by_id_not_found(self, repository_mock, service):
        resource = DummyMaasBaseModel(id=0)
        repository_mock.get_by_id.return_value = None
        repository_mock.update_by_id.return_value = resource
        builder = ResourceBuilder()
        with pytest.raises(NotFoundException):
            await service.update_by_id(0, builder)

    async def test_update_by_id_etag_matches(self, repository_mock, service):
        resource = DummyMaasBaseModel(id=0)
        repository_mock.get_by_id.return_value = resource
        repository_mock.update_by_id.return_value = resource
        builder = ResourceBuilder()
        result = await service.update_by_id(0, builder, "test")
        repository_mock.get_by_id.assert_awaited_once_with(id=0)
        repository_mock.update_by_id.assert_awaited_once_with(
            id=0, builder=builder
        )
        assert result == resource

    async def test_update_by_id_etag_not_matching(
        self, repository_mock, service
    ):
        resource = DummyMaasBaseModel(id=0)
        repository_mock.get_by_id.return_value = resource
        repository_mock.update_by_id.return_value = resource
        builder = ResourceBuilder()
        with pytest.raises(PreconditionFailedException):
            await service.update_by_id(0, builder, "not a match")
        repository_mock.get_by_id.assert_awaited_once_with(id=0)
        repository_mock.update_by_id.assert_not_called()

    async def test_update_many(self, repository_mock, service):
        resources = [DummyMaasBaseModel(id=0)]
        repository_mock.update_many.return_value = resources
        builder = ResourceBuilder()
        query = QuerySpec()
        results = await service.update_many(query, builder)

        repository_mock.update_many.assert_awaited_once_with(
            query=query, builder=builder
        )
        assert results == resources

    async def test_delete_one(self, repository_mock, service):
        resource = DummyMaasBaseModel(id=0)
        repository_mock.get_one.return_value = resource
        repository_mock.delete_by_id.return_value = resource
        query = QuerySpec()
        result = await service.delete_one(query)
        repository_mock.get_one.assert_awaited_once_with(query=query)
        repository_mock.delete_by_id.assert_awaited_once_with(id=0)
        assert result == resource

    async def test_delete_one_force(self, repository_mock, service):
        resource = DummyMaasBaseModel(id=0)
        repository_mock.get_one.return_value = resource
        repository_mock.delete_by_id.return_value = resource
        query = QuerySpec()

        async def _mock_pre_delete_hook(_):
            raise Exception("BOOM")

        service.pre_delete_hook = _mock_pre_delete_hook

        result = await service.delete_one(query, force=True)
        repository_mock.get_one.assert_awaited_once_with(query=query)
        repository_mock.delete_by_id.assert_awaited_once_with(id=0)
        assert result == resource

    async def test_delete_one_without_force(self, repository_mock, service):
        resource = DummyMaasBaseModel(id=0)
        repository_mock.get_one.return_value = resource
        repository_mock.delete_by_id.return_value = resource
        query = QuerySpec()

        async def _mock_pre_delete_hook(_):
            raise Exception("BOOM")

        service.pre_delete_hook = _mock_pre_delete_hook

        with pytest.raises(Exception):
            await service.delete_one(query)

    async def test_delete_one_not_found(self, repository_mock, service):
        resource = DummyMaasBaseModel(id=0)
        repository_mock.get_one.return_value = None
        repository_mock.delete_by_id.return_value = resource
        query = QuerySpec()
        resource = await service.delete_one(query)
        assert resource is None
        repository_mock.get_one.assert_awaited_once_with(query=query)
        repository_mock.delete_by_id.assert_not_called()

    async def test_delete_one_etag_matches(self, repository_mock, service):
        resource = DummyMaasBaseModel(id=0)
        repository_mock.get_one.return_value = resource
        repository_mock.delete_by_id.return_value = resource
        query = QuerySpec()
        result = await service.delete_one(query, "test")
        repository_mock.get_one.assert_awaited_once_with(query=query)
        repository_mock.delete_by_id.assert_awaited_once_with(id=0)
        assert result == resource

    async def test_delete_one_etag_not_matching(
        self, repository_mock, service
    ):
        resource = DummyMaasBaseModel(id=0)
        repository_mock.get_one.return_value = resource
        repository_mock.delete_one.return_value = resource
        query = QuerySpec()
        with pytest.raises(PreconditionFailedException):
            await service.delete_one(query, "not a match")
        repository_mock.get_one.assert_awaited_once_with(query=query)
        repository_mock.delete_by_id.assert_not_called()

    async def test_delete_by_id(self, repository_mock, service):
        resource = DummyMaasBaseModel(id=0)
        repository_mock.get_by_id.return_value = resource
        repository_mock.delete_by_id.return_value = resource
        result = await service.delete_by_id(0)
        repository_mock.get_by_id.assert_awaited_once_with(id=0)
        repository_mock.delete_by_id.assert_awaited_once_with(id=0)
        assert result == resource

    async def test_delete_by_id_force(self, repository_mock, service):
        resource = DummyMaasBaseModel(id=0)
        repository_mock.get_by_id.return_value = resource
        repository_mock.delete_by_id.return_value = resource

        async def _mock_pre_delete_hook(_):
            raise Exception("BOOM")

        service.pre_delete_hook = _mock_pre_delete_hook

        result = await service.delete_by_id(id=0, force=True)
        repository_mock.get_by_id.assert_awaited_once_with(id=0)
        repository_mock.delete_by_id.assert_awaited_once_with(id=0)
        assert result == resource

    async def test_delete_by_id_without_force(self, repository_mock, service):
        resource = DummyMaasBaseModel(id=0)
        repository_mock.get_by_id.return_value = resource
        repository_mock.delete_by_id.return_value = resource

        async def _mock_pre_delete_hook(_):
            raise Exception("BOOM")

        service.pre_delete_hook = _mock_pre_delete_hook

        with pytest.raises(Exception):
            await service.delete_by_id(0)

    async def test_delete_by_id_not_found(self, repository_mock, service):
        resource = DummyMaasBaseModel(id=0)
        repository_mock.get_by_id.return_value = None
        repository_mock.delete_by_id.return_value = resource
        resource = await service.delete_by_id(0)
        assert resource is None
        repository_mock.get_by_id.assert_awaited_once_with(id=0)
        repository_mock.delete_by_id.assert_not_called()

    async def test_delete_by_id_etag_matches(self, repository_mock, service):
        resource = DummyMaasBaseModel(id=0)
        repository_mock.get_by_id.return_value = resource
        repository_mock.delete_by_id.return_value = resource
        result = await service.delete_by_id(0, "test")
        repository_mock.get_by_id.assert_awaited_once_with(id=0)
        repository_mock.delete_by_id.assert_awaited_once_with(id=0)
        assert result == resource

    async def test_delete_by_id_etag_not_matching(
        self, repository_mock, service
    ):
        resource = DummyMaasBaseModel(id=0)
        repository_mock.get_by_id.return_value = resource
        repository_mock.delete_by_id.return_value = resource
        with pytest.raises(PreconditionFailedException):
            await service.delete_by_id(0, "not a match")
        repository_mock.get_by_id.assert_awaited_once_with(id=0)
        repository_mock.delete_by_id.assert_not_called()

    async def test_delete_many(self, repository_mock, service):
        resources = [DummyMaasBaseModel(id=0)]
        repository_mock.delete_many.return_value = resources
        query = QuerySpec()
        results = await service.delete_many(query)

        repository_mock.delete_many.assert_awaited_once_with(query=query)
        assert results == resources
