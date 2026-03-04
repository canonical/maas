# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest
from sqlalchemy import and_
from sqlalchemy.sql.operators import eq

from maasservicelayer.builders.openfga_tuple import OpenFGATupleBuilder
from maasservicelayer.builders.usergroups import UserGroupBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.usergroups import (
    UserGroupsClauseFactory,
    UserGroupsRepository,
)
from maasservicelayer.db.repositories.usergroups_members import (
    UserGroupMembersRepository,
)
from maasservicelayer.db.tables import OpenFGATupleTable
from maasservicelayer.models.base import MaasBaseModel
from maasservicelayer.models.usergroup_members import UserGroupMember
from maasservicelayer.models.usergroups import UserGroup
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.openfga_tuples import OpenFGATupleService
from maasservicelayer.services.usergroups import (
    UserAlreadyInGroup,
    UserGroupNotFound,
    UserGroupsService,
)
from maasservicelayer.utils.date import utcnow
from tests.fixtures.factories.openfga_tuples import create_openfga_tuple
from tests.fixtures.factories.user import create_test_user
from tests.fixtures.factories.usergroups import create_test_usergroup
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.services.base import ServiceCommonTests

TEST_GROUP = UserGroup(
    id=1,
    name="test_group",
    description="test_description",
    created=utcnow(),
    updated=utcnow(),
)


@pytest.mark.asyncio
class TestCommonUserGroupsService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BaseService:
        return UserGroupsService(
            context=Context(),
            usergroups_repository=Mock(UserGroupsRepository),
            usergroup_members_repository=Mock(UserGroupMembersRepository),
            openfga_tuples_service=Mock(OpenFGATupleService),
        )

    @pytest.fixture
    def test_instance(self) -> MaasBaseModel:
        return TEST_GROUP

    async def test_delete_many(
        self, service_instance, test_instance: MaasBaseModel
    ):
        with pytest.raises(NotImplementedError):
            await super().test_delete_many(service_instance, test_instance)


@pytest.mark.asyncio
class TestUserGroupsService:
    async def test_add_user_to_group(self) -> None:
        usergroups_repository = Mock(UserGroupsRepository)
        usergroups_repository.get_one.return_value = TEST_GROUP
        usergroup_members_repository = Mock(UserGroupMembersRepository)
        usergroup_members_repository.exists.return_value = False
        openfga_tuples_service = Mock(OpenFGATupleService)

        service = UserGroupsService(
            context=Context(),
            usergroups_repository=usergroups_repository,
            usergroup_members_repository=usergroup_members_repository,
            openfga_tuples_service=openfga_tuples_service,
        )

        await service.add_user_to_group(1, TEST_GROUP.name)
        usergroups_repository.get_one.assert_awaited_once()
        usergroup_members_repository.exists.assert_awaited_once()
        openfga_tuples_service.create.assert_awaited_once_with(
            OpenFGATupleBuilder.build_user_member_group(1, TEST_GROUP.id)
        )

    async def test_add_user_to_group_raises_if_already_member(self) -> None:
        usergroups_repository = Mock(UserGroupsRepository)
        usergroups_repository.get_one.return_value = TEST_GROUP
        usergroup_members_repository = Mock(UserGroupMembersRepository)
        usergroup_members_repository.exists.return_value = True
        openfga_tuples_service = Mock(OpenFGATupleService)

        service = UserGroupsService(
            context=Context(),
            usergroups_repository=usergroups_repository,
            usergroup_members_repository=usergroup_members_repository,
            openfga_tuples_service=openfga_tuples_service,
        )

        with pytest.raises(UserAlreadyInGroup):
            await service.add_user_to_group(1, TEST_GROUP.name)

        usergroups_repository.get_one.assert_awaited_once()
        usergroup_members_repository.exists.assert_awaited_once()
        openfga_tuples_service.create.assert_not_awaited()

    async def test_delete_by_id(self) -> None:
        usergroups_repository = Mock(UserGroupsRepository)
        usergroups_repository.delete_by_id.return_value = TEST_GROUP
        usergroups_repository.get_by_id.side_effect = [TEST_GROUP, None]
        openfga_tuples_service = Mock(OpenFGATupleService)

        service = UserGroupsService(
            context=Context(),
            usergroups_repository=usergroups_repository,
            usergroup_members_repository=Mock(UserGroupMembersRepository),
            openfga_tuples_service=openfga_tuples_service,
        )

        await service.delete_by_id(TEST_GROUP.id)
        usergroups_repository.delete_by_id.assert_awaited_once_with(
            id=TEST_GROUP.id
        )
        openfga_tuples_service.delete_group.assert_awaited_once_with(
            TEST_GROUP.id
        )

    async def test_add_user_to_group_by_id(self) -> None:
        usergroups_repository = Mock(UserGroupsRepository)
        usergroups_repository.get_by_id.return_value = TEST_GROUP
        usergroup_members_repository = Mock(UserGroupMembersRepository)
        usergroup_members_repository.exists.return_value = False
        openfga_tuples_service = Mock(OpenFGATupleService)

        service = UserGroupsService(
            context=Context(),
            usergroups_repository=usergroups_repository,
            usergroup_members_repository=usergroup_members_repository,
            openfga_tuples_service=openfga_tuples_service,
        )

        await service.add_user_to_group_by_id(1, TEST_GROUP.id)
        usergroups_repository.get_by_id.assert_awaited_once_with(
            id=TEST_GROUP.id
        )
        usergroup_members_repository.exists.assert_awaited_once()
        openfga_tuples_service.create.assert_awaited_once_with(
            OpenFGATupleBuilder.build_user_member_group(1, TEST_GROUP.id)
        )

    async def test_add_user_to_group_by_id_raises_if_already_member(
        self,
    ) -> None:
        usergroups_repository = Mock(UserGroupsRepository)
        usergroups_repository.get_by_id.return_value = TEST_GROUP
        usergroup_members_repository = Mock(UserGroupMembersRepository)
        usergroup_members_repository.exists.return_value = True
        openfga_tuples_service = Mock(OpenFGATupleService)

        service = UserGroupsService(
            context=Context(),
            usergroups_repository=usergroups_repository,
            usergroup_members_repository=usergroup_members_repository,
            openfga_tuples_service=openfga_tuples_service,
        )

        with pytest.raises(UserAlreadyInGroup):
            await service.add_user_to_group_by_id(1, TEST_GROUP.id)
        usergroups_repository.get_by_id.assert_awaited_once_with(
            id=TEST_GROUP.id
        )
        usergroup_members_repository.exists.assert_awaited_once()
        openfga_tuples_service.create.assert_not_awaited()

    async def test_add_user_to_group_by_id_not_found(self) -> None:
        usergroups_repository = Mock(UserGroupsRepository)
        usergroups_repository.get_by_id.return_value = None

        service = UserGroupsService(
            context=Context(),
            usergroups_repository=usergroups_repository,
            usergroup_members_repository=Mock(UserGroupMembersRepository),
            openfga_tuples_service=Mock(OpenFGATupleService),
        )

        with pytest.raises(UserGroupNotFound):
            await service.add_user_to_group_by_id(1, 999)

    async def test_list_usergroup_members(self) -> None:
        members = [
            UserGroupMember(
                id=10, group_id=1, username="user1", email="u1@test.com"
            ),
            UserGroupMember(
                id=20, group_id=1, username="user2", email="u2@test.com"
            ),
        ]
        usergroup_members_repository = Mock(UserGroupMembersRepository)
        usergroup_members_repository.list_all.return_value = members

        service = UserGroupsService(
            context=Context(),
            usergroups_repository=Mock(UserGroupsRepository),
            usergroup_members_repository=usergroup_members_repository,
            openfga_tuples_service=Mock(OpenFGATupleService),
        )

        result = await service.list_usergroup_members(1)
        assert result == members
        usergroup_members_repository.list_all.assert_awaited_once()

    async def test_remove_user_from_group(self) -> None:
        openfga_tuples_service = Mock(OpenFGATupleService)

        service = UserGroupsService(
            context=Context(),
            usergroups_repository=Mock(UserGroupsRepository),
            usergroup_members_repository=Mock(UserGroupMembersRepository),
            openfga_tuples_service=openfga_tuples_service,
        )

        await service.remove_user_from_group(1, 10)
        openfga_tuples_service.remove_user_from_group.assert_awaited_once_with(
            1, 10
        )


@pytest.mark.asyncio
class TestIntegrationUserGroupsService:
    async def test_add_user_to_group(
        self, fixture: Fixture, services: ServiceCollectionV3
    ):
        group = await create_test_usergroup(
            fixture, name="integration-group", description="test"
        )
        user = await create_test_user(fixture)

        await services.usergroups.add_user_to_group(user.id, group.name)

        membership_tuples = await fixture.get(
            OpenFGATupleTable.fullname,
            and_(
                eq(OpenFGATupleTable.c._user, f"user:{user.id}"),
                eq(OpenFGATupleTable.c.relation, "member"),
                eq(OpenFGATupleTable.c.object_type, "group"),
                eq(OpenFGATupleTable.c.object_id, str(group.id)),
            ),
        )
        assert len(membership_tuples) == 1

    async def test_add_user_to_nonexistent_group(
        self, services: ServiceCollectionV3
    ):
        with pytest.raises(UserGroupNotFound):
            await services.usergroups.add_user_to_group(1, "foo")

    async def test_delete_by_id_cleans_openfga_tuples(
        self,
        fixture: Fixture,
        services: ServiceCollectionV3,
    ) -> None:
        group = await create_test_usergroup(
            fixture, name="integration-group", description="test"
        )

        # add users to group
        await create_openfga_tuple(
            fixture, "user:10", "user", "member", "group", str(group.id)
        )
        await create_openfga_tuple(
            fixture, "user:20", "user", "member", "group", str(group.id)
        )

        # grant permissions to group
        await create_openfga_tuple(
            fixture,
            f"group:{group.id}#member",
            "group",
            "can_edit",
            "machine",
            "100",
        )
        await create_openfga_tuple(
            fixture,
            f"group:{group.id}#member",
            "group",
            "can_view",
            "pool",
            "200",
        )

        # create another group and tuple that should not be affected by the deletion of the first group
        await create_openfga_tuple(
            fixture, "user:99", "user", "member", "group", "9999"
        )

        await services.usergroups.delete_by_id(group.id)

        # openfga tuples are gone
        membership_tuples = await fixture.get(
            OpenFGATupleTable.fullname,
            and_(
                eq(OpenFGATupleTable.c.object_type, "group"),
                eq(OpenFGATupleTable.c.object_id, str(group.id)),
            ),
        )
        assert len(membership_tuples) == 0

        entitlement_tuples = await fixture.get(
            OpenFGATupleTable.fullname,
            eq(OpenFGATupleTable.c._user, f"group:{group.id}#member"),
        )
        assert len(entitlement_tuples) == 0

        # other tuples are unaffected
        unrelated_tuples = await fixture.get(
            OpenFGATupleTable.fullname,
            and_(
                eq(OpenFGATupleTable.c.object_type, "group"),
                eq(OpenFGATupleTable.c.object_id, "9999"),
                eq(OpenFGATupleTable.c._user, "user:99"),
            ),
        )
        assert len(unrelated_tuples) == 1

    async def test_create_group(
        self,
        fixture: Fixture,
        services: ServiceCollectionV3,
    ) -> None:
        group = await services.usergroups.create(
            UserGroupBuilder(
                name="created-via-service",
                description="integration test",
            )
        )
        assert group.name == "created-via-service"
        assert group.description == "integration test"
        assert group.id is not None

        retrieved = await services.usergroups.get_by_id(group.id)
        assert retrieved is not None
        assert retrieved.name == "created-via-service"

    async def test_default_user_group_exists(
        self,
        fixture: Fixture,
        services: ServiceCollectionV3,
    ) -> None:
        exists = await services.usergroups.exists(
            query=QuerySpec(where=UserGroupsClauseFactory.with_name("Users"))
        )
        assert exists is True

    async def test_default_administrator_group_exists(
        self,
        fixture: Fixture,
        services: ServiceCollectionV3,
    ) -> None:
        exists = await services.usergroups.exists(
            query=QuerySpec(
                where=UserGroupsClauseFactory.with_name("Administrators")
            )
        )
        assert exists is True

    async def test_list_usergroup_members(
        self,
        fixture: Fixture,
        services: ServiceCollectionV3,
    ) -> None:
        group = await create_test_usergroup(
            fixture, name="members-group", description="test"
        )
        user1 = await create_test_user(
            fixture, username="member1", email="mail1@example.com"
        )
        user2 = await create_test_user(
            fixture, username="member2", email="mail2@example.com"
        )

        await create_openfga_tuple(
            fixture,
            f"user:{user1.id}",
            "user",
            "member",
            "group",
            str(group.id),
        )
        await create_openfga_tuple(
            fixture,
            f"user:{user2.id}",
            "user",
            "member",
            "group",
            str(group.id),
        )

        members = await services.usergroups.list_usergroup_members(group.id)
        assert len(members) == 2
        usernames = {m.username for m in members}
        assert usernames == {"member1", "member2"}

    async def test_list_usergroup_members_empty(
        self,
        fixture: Fixture,
        services: ServiceCollectionV3,
    ) -> None:
        group = await create_test_usergroup(
            fixture, name="empty-group", description="test"
        )
        members = await services.usergroups.list_usergroup_members(group.id)
        assert len(members) == 0

    async def test_remove_user_from_group(
        self,
        fixture: Fixture,
        services: ServiceCollectionV3,
    ) -> None:
        group = await create_test_usergroup(
            fixture, name="remove-group", description="test"
        )
        user = await create_test_user(fixture, username="to-remove")

        await create_openfga_tuple(
            fixture,
            f"user:{user.id}",
            "user",
            "member",
            "group",
            str(group.id),
        )

        members_before = await services.usergroups.list_usergroup_members(
            group.id
        )
        assert len(members_before) == 1

        await services.usergroups.remove_user_from_group(group.id, user.id)

        membership_tuples = await fixture.get(
            OpenFGATupleTable.fullname,
            and_(
                eq(OpenFGATupleTable.c._user, f"user:{user.id}"),
                eq(OpenFGATupleTable.c.relation, "member"),
                eq(OpenFGATupleTable.c.object_type, "group"),
                eq(OpenFGATupleTable.c.object_id, str(group.id)),
            ),
        )
        assert len(membership_tuples) == 0

    async def test_add_user_to_group_by_id(
        self,
        fixture: Fixture,
        services: ServiceCollectionV3,
    ) -> None:
        group = await create_test_usergroup(
            fixture, name="add-by-id-group", description="test"
        )
        user = await create_test_user(fixture)

        await services.usergroups.add_user_to_group_by_id(user.id, group.id)

        membership_tuples = await fixture.get(
            OpenFGATupleTable.fullname,
            and_(
                eq(OpenFGATupleTable.c._user, f"user:{user.id}"),
                eq(OpenFGATupleTable.c.relation, "member"),
                eq(OpenFGATupleTable.c.object_type, "group"),
                eq(OpenFGATupleTable.c.object_id, str(group.id)),
            ),
        )
        assert len(membership_tuples) == 1

    async def test_add_user_to_group_by_id_not_found(
        self,
        services: ServiceCollectionV3,
    ) -> None:
        with pytest.raises(UserGroupNotFound):
            await services.usergroups.add_user_to_group_by_id(1, 99999)
