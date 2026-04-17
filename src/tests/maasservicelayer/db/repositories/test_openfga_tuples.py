# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.openfga import OPENFGA_STORE_ID
from maasservicelayer.builders.openfga_tuple import OpenFGATupleBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.openfga_tuples import (
    OpenFGATuplesClauseFactory,
    OpenFGATuplesRepository,
)
from maasservicelayer.db.tables import OpenFGATupleTable
from tests.fixtures.factories.openfga_tuples import create_openfga_tuple
from tests.maasapiserver.fixtures.db import Fixture
from tests.utils.ulid import is_ulid


class TestOpenFGATuplesClauseFactory:
    def test_with_object_type(self) -> None:
        clause = OpenFGATuplesClauseFactory.with_object_type("type")
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("openfga.tuple.object_type = 'type'")

    def test_with_object_id(self) -> None:
        clause = OpenFGATuplesClauseFactory.with_object_id("id")
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("openfga.tuple.object_id = 'id'")

    def test_with_relation(self):
        clause = OpenFGATuplesClauseFactory.with_relation("relation")
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("openfga.tuple.relation = 'relation'")

    def test_with_user(self):
        clause = OpenFGATuplesClauseFactory.with_user("user:user")
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("openfga.tuple._user = 'user:user'")

    def test_with_users(self) -> None:
        clause = OpenFGATuplesClauseFactory.with_users(
            ["user:1", "user:2", "user:3"]
        )
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("openfga.tuple._user IN ('user:1', 'user:2', 'user:3')")

    def test_with_entitlement_tuples(self) -> None:
        clause = OpenFGATuplesClauseFactory.with_entitlement_tuples(
            [
                ("can_view_machines", "pool", "1"),
                ("can_edit_machines", "pool", "2"),
            ]
        )
        sql_str = str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        )
        assert "can_view_machines" in sql_str
        assert "can_edit_machines" in sql_str
        assert "'pool'" in sql_str
        assert "'1'" in sql_str
        assert "'2'" in sql_str


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestOpenFGATuplesRepository:
    async def test_upsert(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        repository = OpenFGATuplesRepository(Context(connection=db_connection))
        t = await repository.upsert(
            OpenFGATupleBuilder(
                user="user:alice",
                user_type="user",
                relation="member",
                object_type="group",
                object_id="admins",
            )
        )

        assert t.user == "user:alice"
        assert t.relation == "member"
        assert t.user_type == "user"
        assert t.object_id == "admins"
        assert t.object_type == "group"

        tuples = await fixture.get(
            OpenFGATupleTable.fullname,
            eq(OpenFGATupleTable.c.relation, "member"),
        )
        assert len(tuples) == 1
        tuple_dict = tuples[0]
        assert tuple_dict["_user"] == "user:alice"
        assert tuple_dict["relation"] == "member"
        assert tuple_dict["object_type"] == "group"
        assert tuple_dict["object_id"] == "admins"
        assert tuple_dict["store"] == OPENFGA_STORE_ID
        assert is_ulid(tuple_dict["ulid"]) is True
        assert tuple_dict["inserted_at"] is not None
        assert tuple_dict["condition_name"] is None
        assert tuple_dict["condition_context"] is None

    async def test_upsert_replaces_tuple(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        repository = OpenFGATuplesRepository(Context(connection=db_connection))

        await create_openfga_tuple(
            fixture,
            user="user:1",
            user_type="user",
            relation="member",
            object_type="group",
            object_id="0",
        )

        t = await repository.upsert(
            OpenFGATupleBuilder(
                user="user:1",
                user_type="user",
                relation="member",
                object_type="group",
                object_id="0",
            )
        )

        assert t.user == "user:1"
        assert t.relation == "member"
        assert t.user_type == "user"
        assert t.object_id == "0"
        assert t.object_type == "group"

    async def test_delete_many(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        repository = OpenFGATuplesRepository(Context(connection=db_connection))

        await create_openfga_tuple(
            fixture,
            user="user:alice",
            user_type="user",
            relation="member",
            object_type="group",
            object_id="admins",
        )
        await create_openfga_tuple(
            fixture,
            user="user:bob",
            user_type="user",
            relation="member",
            object_type="group",
            object_id="admins",
        )

        await repository.delete_many(QuerySpec())

        tuples = await fixture.get(
            OpenFGATupleTable.fullname,
            eq(OpenFGATupleTable.c.relation, "member"),
        )
        assert len(tuples) == 0

    async def test_bulk_upsert(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        repository = OpenFGATuplesRepository(Context(connection=db_connection))

        builders = [
            OpenFGATupleBuilder(
                user=f"user:{i}",
                user_type="user",
                relation="member",
                object_type="group",
                object_id="bulk-group",
            )
            for i in range(1, 4)
        ]
        await repository.bulk_upsert(builders)

        tuples = await fixture.get(
            OpenFGATupleTable.fullname,
            eq(OpenFGATupleTable.c.object_id, "bulk-group"),
        )
        assert len(tuples) == 3
        users = {t["_user"] for t in tuples}
        assert users == {"user:1", "user:2", "user:3"}
        assert all(t["store"] == OPENFGA_STORE_ID for t in tuples)
        assert all(is_ulid(t["ulid"]) for t in tuples)

    async def test_list_entitlements(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        repository = OpenFGATuplesRepository(Context(connection=db_connection))

        await create_openfga_tuple(
            fixture,
            user="group:10#member",
            user_type="userset",
            relation="can_edit_machines",
            object_type="maas",
            object_id="0",
        )
        await create_openfga_tuple(
            fixture,
            user="group:10#member",
            user_type="userset",
            relation="can_view_machines",
            object_type="pool",
            object_id="5",
        )
        # unrelated group that should not appear
        await create_openfga_tuple(
            fixture,
            user="group:20#member",
            user_type="userset",
            relation="can_edit_machines",
            object_type="maas",
            object_id="0",
        )

        query = QuerySpec(
            where=OpenFGATuplesClauseFactory.with_user("group:10#member")
        )
        first_page = await repository.list_entitlements(
            page=1, size=1, query=query
        )
        assert first_page.total == 2
        assert len(first_page.items) == 1

        second_page = await repository.list_entitlements(
            page=2, size=1, query=query
        )
        assert second_page.total == 2
        assert len(second_page.items) == 1

        all_relations = {
            first_page.items[0].relation,
            second_page.items[0].relation,
        }
        assert all_relations == {"can_edit_machines", "can_view_machines"}
        assert all(
            t.user == "group:10#member"
            for t in first_page.items + second_page.items
        )
