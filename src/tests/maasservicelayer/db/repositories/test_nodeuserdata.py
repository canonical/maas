#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.nodeuserdata import NodeUserDataBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.nodeuserdata import (
    NodeUserDataClauseFactory,
    NodeUserDataRepository,
)
from maasservicelayer.db.tables import NodeUserDataTable
from maasservicelayer.models.nodeuserdata import NodeUserData
from tests.fixtures.factories.node import create_test_machine_entry
from tests.fixtures.factories.nodeuserdata import (
    create_test_nodeuserdata_entry,
)
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestNodeUserDataClauseFactory:
    def test_with_node_id(self) -> None:
        clause = NodeUserDataClauseFactory.with_node_id(1)
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_nodeuserdata.node_id = 1"
        )

    def test_with_for_ephemeral_environment(self) -> None:
        clause = NodeUserDataClauseFactory.with_for_ephemeral_environment(True)
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_nodeuserdata.for_ephemeral_environment = true"
        )


class TestNodeUserDataRepository(RepositoryCommonTests[NodeUserData]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> NodeUserDataRepository:
        return NodeUserDataRepository(
            context=Context(connection=db_connection)
        )

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[NodeUserData]:
        entries = []
        for i in range(num_objects):
            node = await create_test_machine_entry(fixture)
            entries.append(
                await create_test_nodeuserdata_entry(
                    fixture, node["id"], data=f"user-data-{i}".encode()
                )
            )
        return entries

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> NodeUserData:
        node = await create_test_machine_entry(fixture)
        return await create_test_nodeuserdata_entry(fixture, node["id"])

    @pytest.fixture
    async def instance_builder(self, fixture: Fixture) -> NodeUserDataBuilder:
        node = await create_test_machine_entry(fixture)
        return NodeUserDataBuilder(
            node_id=node["id"],
            data=b"user-data",
            for_ephemeral_environment=True,
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[NodeUserDataBuilder]:
        return NodeUserDataBuilder

    @pytest.mark.parametrize("num_objects", [1])
    @pytest.mark.parametrize("page_size", [1])
    async def test_list(
        self, page_size, repository_instance, _setup_test_list, num_objects
    ):
        with pytest.raises(NotImplementedError):
            await super().test_list(
                page_size, repository_instance, _setup_test_list, num_objects
            )

    async def test_list_all(self, repository_instance):
        with pytest.raises(NotImplementedError):
            await repository_instance.list_all()

    async def test_create(self, repository_instance, instance_builder):
        with pytest.raises(NotImplementedError):
            await super().test_create(repository_instance, instance_builder)

    async def test_create_duplicated(
        self, repository_instance, instance_builder
    ):
        with pytest.raises(NotImplementedError):
            await super().test_create_duplicated(
                repository_instance, instance_builder
            )

    async def test_create_many(self, repository_instance, instance_builder):
        with pytest.raises(NotImplementedError):
            await super().test_create_many(
                repository_instance, instance_builder
            )

    async def test_create_many_duplicated(
        self, repository_instance, instance_builder
    ):
        with pytest.raises(NotImplementedError):
            await super().test_create_many_duplicated(
                repository_instance, instance_builder
            )

    async def test_update_by_id(self, repository_instance, instance_builder):
        with pytest.raises(NotImplementedError):
            await repository_instance.update_by_id(1, instance_builder)

    async def test_update_one(self, repository_instance, instance_builder):
        with pytest.raises(NotImplementedError):
            await repository_instance.update_one(QuerySpec(), instance_builder)

    @pytest.mark.parametrize("num_objects", [2])
    async def test_update_one_multiple_results(
        self,
        repository_instance,
        instance_builder_model,
        _setup_test_list,
        num_objects,
    ):
        with pytest.raises(NotImplementedError):
            await super().test_update_one_multiple_results(
                repository_instance,
                instance_builder_model,
                _setup_test_list,
                num_objects,
            )

    @pytest.mark.parametrize("num_objects", [2])
    async def test_update_many(
        self,
        repository_instance,
        instance_builder_model,
        _setup_test_list,
        num_objects,
    ):
        with pytest.raises(NotImplementedError):
            await super().test_update_many(
                repository_instance,
                instance_builder_model,
                _setup_test_list,
                num_objects,
            )

    async def test_upsert_creates_new_entry(
        self,
        repository_instance: NodeUserDataRepository,
        instance_builder: NodeUserDataBuilder,
        fixture: Fixture,
    ) -> None:
        created = await repository_instance.upsert(instance_builder)

        assert created.node_id == instance_builder.node_id
        assert created.data == b"user-data"
        assert created.for_ephemeral_environment is True
        [row] = await fixture.get(
            "maasserver_nodeuserdata", NodeUserDataTable.c.id == created.id
        )
        assert row["data"] == "dXNlci1kYXRh"

    async def test_upsert_overwrites_existing_entry(
        self,
        repository_instance: NodeUserDataRepository,
        created_instance: NodeUserData,
    ) -> None:
        updated = await repository_instance.upsert(
            NodeUserDataBuilder(
                node_id=created_instance.node_id,
                data=b"new-data",
                for_ephemeral_environment=True,
            )
        )

        assert updated.id == created_instance.id
        assert updated.data == b"new-data"

    async def test_upsert_keeps_ephemeral_and_user_env_separate(
        self,
        repository_instance: NodeUserDataRepository,
        created_instance: NodeUserData,
    ) -> None:
        user_env = await repository_instance.upsert(
            NodeUserDataBuilder(
                node_id=created_instance.node_id,
                data=b"deploy-data",
                for_ephemeral_environment=False,
            )
        )

        assert user_env.id != created_instance.id
        assert (
            await repository_instance.get_by_id(created_instance.id)
            == created_instance
        )

    async def test_delete_returns_decoded_data(
        self,
        repository_instance: NodeUserDataRepository,
        created_instance: NodeUserData,
    ) -> None:
        deleted = await repository_instance.delete_by_id(created_instance.id)

        assert deleted == created_instance
