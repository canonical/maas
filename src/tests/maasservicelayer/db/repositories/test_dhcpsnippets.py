# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.dhcpsnippets import (
    DhcpSnippetsRepository,
)
from maasservicelayer.models.dhcpsnippets import DhcpSnippet
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


@pytest.mark.skip(reason="Not implemented yet")
class TestDhcpSnippetsRepository(RepositoryCommonTests[DhcpSnippet]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> DhcpSnippetsRepository:
        return DhcpSnippetsRepository(
            context=Context(connection=db_connection)
        )

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[DhcpSnippet]:
        pass

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> DhcpSnippet:
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
    async def test_get_by_id(self, repository_instance, created_instance):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_get_by_id_not_found(self, repository_instance):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_update(self, repository_instance, instance_builder):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_delete(self, repository_instance, created_instance):
        pass
