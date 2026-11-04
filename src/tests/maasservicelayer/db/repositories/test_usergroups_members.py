# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.usergroups_members import (
    UserGroupMembersRepository,
)
from maasservicelayer.filters.query import QuerySpec
from maasservicelayer.filters.usergroups_members import UserGroupMembersFilters
from maasservicelayer.models.usergroup_members import UserGroupMember
from tests.fixtures.factories.openfga_tuples import create_openfga_tuple
from tests.fixtures.factories.user import create_test_user
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import (
    ReadOnlyRepositoryCommonTests,
)


class TestUserGroupMembersRepository(
    ReadOnlyRepositoryCommonTests[UserGroupMember]
):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> UserGroupMembersRepository:
        return UserGroupMembersRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[UserGroupMember]:
        created_members = []
        for i in range(num_objects):
            user = await create_test_user(
                fixture, username=f"user-{i}", email=f"{i}@example.com"
            )
            await create_openfga_tuple(
                fixture,
                f"user:{user.id}",
                "user",
                "member",
                "group",
                "0",
            )
            created_members.append(
                UserGroupMember(
                    id=user.id,
                    group_id=0,
                    username=user.username,
                    email=user.email,
                )
            )
        return created_members

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> UserGroupMember:
        user = await create_test_user(
            fixture, username="user-0", email="0@example.com"
        )
        await create_openfga_tuple(
            fixture,
            f"user:{user.id}",
            "user",
            "member",
            "group",
            "0",
        )
        return UserGroupMember(
            id=user.id, group_id=0, username="user-0", email="0@example.com"
        )

    async def test_domain_filters_keep_membership_scoped_to_group(
        self, repository_instance: UserGroupMembersRepository, fixture: Fixture
    ) -> None:
        first = await create_test_user(fixture)
        second = await create_test_user(fixture)
        for user, group_id in [(first, 10), (first, 20), (second, 10)]:
            await create_openfga_tuple(
                fixture,
                f"user:{user.id}",
                "user",
                "member",
                "group",
                str(group_id),
            )
        query = QuerySpec(
            where=UserGroupMembersFilters.and_filters(
                [
                    UserGroupMembersFilters.with_ids([first.id]),
                    UserGroupMembersFilters.with_group_id(10),
                ]
            )
        )
        members = await repository_instance.get_many(query)
        assert [(member.id, member.group_id) for member in members] == [
            (first.id, 10)
        ]
