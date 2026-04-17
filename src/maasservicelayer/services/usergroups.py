# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import List

from maasservicelayer.builders.openfga_tuple import OpenFGATupleBuilder
from maasservicelayer.builders.usergroups import UserGroupBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.usergroups import (
    UserGroupsClauseFactory,
    UserGroupsRepository,
)
from maasservicelayer.db.repositories.usergroups_members import (
    UserGroupMembersClauseFactory,
    UserGroupMembersRepository,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.usergroup_members import UserGroupMember
from maasservicelayer.models.usergroups import UserGroup, UserGroupStatistics
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.openfga_tuples import OpenFGATupleService


class UserGroupNotFound(Exception):
    """Raised when a user group is not found in the database."""


class UserAlreadyInGroup(Exception):
    """Raised when a user is already a member of the group."""


class UserGroupsService(
    BaseService[UserGroup, UserGroupsRepository, UserGroupBuilder]
):
    resource_logging_name = "usergroup"

    def __init__(
        self,
        context: Context,
        usergroups_repository: UserGroupsRepository,
        usergroup_members_repository: UserGroupMembersRepository,
        openfga_tuples_service: OpenFGATupleService,
    ):
        super().__init__(context, usergroups_repository)
        self.usergroup_members_repository = usergroup_members_repository
        self.openfga_tuples_service = openfga_tuples_service

    async def post_delete_hook(self, resource: UserGroup) -> None:
        await self.openfga_tuples_service.delete_group(resource.id)

    async def post_delete_many_hook(self, resources: List[UserGroup]) -> None:
        raise NotImplementedError(
            "Deleting multiple user groups is not supported."
        )

    # User management methods.
    async def _check_already_member(self, user_id: int, group_id: int) -> None:
        exists = await self.usergroup_members_repository.exists(
            QuerySpec(
                where=UserGroupMembersClauseFactory.and_clauses(
                    [
                        UserGroupMembersClauseFactory.with_group_id(group_id),
                        UserGroupMembersClauseFactory.with_id(user_id),
                    ]
                )
            )
        )
        if exists:
            raise UserAlreadyInGroup(
                f"User {user_id} is already a member of group {group_id}."
            )

    async def add_user_to_group(self, user_id: int, group_name: str):
        group = await self.get_one(
            QuerySpec(where=UserGroupsClauseFactory.with_name(group_name))
        )
        if group is None:
            raise UserGroupNotFound()

        await self._check_already_member(user_id, group.id)
        await self.openfga_tuples_service.upsert(
            OpenFGATupleBuilder.build_user_member_group(user_id, group.id)
        )

    async def add_user_to_group_by_id(self, user_id: int, group_id: int):
        group = await self.get_by_id(group_id)
        if group is None:
            raise UserGroupNotFound()

        await self._check_already_member(user_id, group_id)
        await self.openfga_tuples_service.upsert(
            OpenFGATupleBuilder.build_user_member_group(user_id, group.id)
        )

    async def list_usergroup_members(
        self, group_id: int
    ) -> List[UserGroupMember]:
        return await self.usergroup_members_repository.list_all(
            QuerySpec(
                where=UserGroupMembersClauseFactory.with_group_id(group_id)
            )
        )

    async def list_usergroup_members_page(
        self, group_id: int, page: int, size: int
    ) -> ListResult[UserGroupMember]:
        return await self.usergroup_members_repository.list(
            page=page,
            size=size,
            query=QuerySpec(
                where=UserGroupMembersClauseFactory.with_group_id(group_id)
            ),
        )

    async def list_groups_statistics(
        self,
        page: int,
        size: int,
        query: QuerySpec | None = None,
    ) -> ListResult[UserGroupStatistics]:
        return await self.repository.list_groups_statistics(
            page=page, size=size, query=query
        )

    async def remove_user_from_group(self, group_id: int, user_id: int):
        await self.openfga_tuples_service.remove_user_from_group(
            group_id, user_id
        )

    async def bulk_add_users_to_group(
        self, group_id: int, user_ids: List[int]
    ) -> None:
        already_member = await self.usergroup_members_repository.exists(
            QuerySpec(
                where=UserGroupMembersClauseFactory.and_clauses(
                    [
                        UserGroupMembersClauseFactory.with_group_id(group_id),
                        UserGroupMembersClauseFactory.with_ids(user_ids),
                    ]
                )
            )
        )
        if already_member:
            raise UserAlreadyInGroup(
                "One or more users are already members of the group."
            )
        await self.openfga_tuples_service.bulk_add_users_to_group(
            group_id, user_ids
        )

    async def bulk_remove_users_from_group(
        self, group_id: int, user_ids: List[int]
    ) -> None:
        await self.openfga_tuples_service.bulk_remove_users_from_group(
            group_id, user_ids
        )
