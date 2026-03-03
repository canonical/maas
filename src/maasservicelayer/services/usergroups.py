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
from maasservicelayer.models.usergroups import UserGroup
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.openfga_tuples import OpenFGATupleService


class UserGroupNotFound(Exception):
    """Raised when a user group is not found in the database."""


class UserGroupsService(
    BaseService[UserGroup, UserGroupsRepository, UserGroupBuilder]
):
    resource_logging_name = "usergroup"

    def __init__(
        self,
        context: Context,
        usergroups_repository: UserGroupsRepository,
        openfga_tuples_service: OpenFGATupleService,
    ):
        super().__init__(context, usergroups_repository)
        self.openfga_tuples_service = openfga_tuples_service

    async def add_user_to_group(self, user_id: int, group_name: str):
        group = await self.get_one(
            QuerySpec(where=UserGroupsClauseFactory.with_name(group_name))
        )
        if group is None:
            raise UserGroupNotFound()

        await self.openfga_tuples_service.create(
            OpenFGATupleBuilder.build_user_member_group(user_id, group.id)
        )

    async def post_delete_hook(self, resource: UserGroup) -> None:
        await self.openfga_tuples_service.delete_group(resource.id)

    async def post_delete_many_hook(self, resources: List[UserGroup]) -> None:
        raise NotImplementedError(
            "Deleting multiple user groups is not supported."
        )
