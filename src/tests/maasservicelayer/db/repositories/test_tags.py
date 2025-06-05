# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.tags import TagBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.tags import TagsRepository
from maasservicelayer.db.tables import NodeTagTable
from maasservicelayer.models.tags import Tag
from tests.fixtures.factories.node import create_test_machine_entry
from tests.fixtures.factories.tag import (
    create_test_tag_entry,
    create_test_tag_node_relationship,
)
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestTagRepository(RepositoryCommonTests[Tag]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> TagsRepository:
        return TagsRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[Tag]:
        return [
            Tag(
                **await create_test_tag_entry(
                    fixture, name=f"test-tag-{i}", definition="//node"
                )
            )
            for i in range(num_objects)
        ]

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> Tag:
        return Tag(
            **await create_test_tag_entry(
                fixture, name="test-tag", definition="//node"
            )
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[TagBuilder]:
        return TagBuilder

    @pytest.fixture
    async def instance_builder(self, *args, **kwargs) -> TagBuilder:
        return TagBuilder(
            name="new-test-tag",
            definition="//node",
            comment="comment",
            kernel_opts="",
        )

    async def test_delete_nodes_relationship(
        self,
        repository_instance: TagsRepository,
        created_instance: Tag,
        fixture: Fixture,
    ) -> None:
        node = await create_test_machine_entry(fixture)
        await create_test_tag_node_relationship(
            fixture, node_id=node["id"], tag_id=created_instance.id
        )
        await repository_instance.delete_nodes_relationship_for_tag(
            created_instance
        )
        rows = await fixture.get(
            NodeTagTable.name, eq(NodeTagTable.c.tag_id, created_instance.id)
        )
        assert len(rows) == 0
