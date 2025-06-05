# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq

from sqlalchemy import delete, Table

from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import NodeTagTable, TagTable
from maasservicelayer.models.tags import Tag


class TagsRepository(BaseRepository[Tag]):
    def get_repository_table(self) -> Table:
        return TagTable

    def get_model_factory(self) -> type[Tag]:
        return Tag

    async def delete_nodes_relationship_for_tag(self, tag: Tag) -> None:
        stmt = delete(NodeTagTable).where(eq(NodeTagTable.c.tag_id, tag.id))
        await self.execute_stmt(stmt)
