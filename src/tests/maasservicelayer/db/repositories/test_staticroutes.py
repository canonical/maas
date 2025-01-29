# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.staticroutes import (
    StaticRoutesRepository,
)
from maasservicelayer.models.staticroutes import StaticRoute
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestStaticRoutesRepository(RepositoryCommonTests[StaticRoute]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> StaticRoutesRepository:
        return StaticRoutesRepository(
            context=Context(connection=db_connection)
        )

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[StaticRoute]:
        pass

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> StaticRoute:
        pass

    @pytest.fixture
    async def instance_builder_model(self, *args, **kwargs):
        pass

    @pytest.fixture
    async def instance_builder(self, *args, **kwargs):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_list(
        self, page_size, repository_instance, _setup_test_list, num_objects
    ):
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
    async def test_exists_found(self, repository_instance, created_instance):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_exists_not_found(self, repository_instance):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_get_one(self, repository_instance, created_instance):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_get_one_multiple_results(self, repository_instance):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_get_many(self, repository_instance, created_instance):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_get_by_id(self, repository_instance, created_instance):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_get_by_id_not_found(self, repository_instance):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_delete_one(self, repository_instance, created_instance):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_delete_one_multiple_results(
        self, repository_instance, created_instance
    ):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_delete_by_id(self, repository_instance, created_instance):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_delete_many(self, repository_instance, created_instance):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_update_by_id(self, repository_instance, instance_builder):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_update_one(self, repository_instance, instance_builder):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_update_one_multiple_results(
        self, repository_instance, instance_builder
    ):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_update_many(self, repository_instance, instance_builder):
        pass
