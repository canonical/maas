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


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestOpenFGATuplesRepository:
    async def test_create(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        repository = OpenFGATuplesRepository(Context(connection=db_connection))
        t = await repository.create(
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
