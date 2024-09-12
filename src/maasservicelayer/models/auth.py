#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import BaseModel, Field

from maasservicelayer.auth.jwt import UserRole


class AuthenticatedUser(BaseModel):
    """Represents the currently logged-in user with their permissions.

    Attributes:
        username (str): the username of the user
        roles (UserRole): local roles that the user has, i.e. user or admin
        visible_pools (set[int]): pools where the user can see machines either
            unowned or owned by theirselves (RBAC)
        view_all_pools (set[int]): pools where the user can see all machines
            even if the machine is owned by a different user (RBAC)
        deploy_pools (set[int]): pools where the user can deploy machines (RBAC)
        admin_pools (set[int]): pools where the user can admin machines (RBAC)
        edit_pools (set[int]): pools that the user can edit (RBAC)
    """

    username: str
    roles: set[UserRole]
    visible_pools: set[int] = Field(default_factory=set)
    view_all_pools: set[int] = Field(default_factory=set)
    deploy_pools: set[int] = Field(default_factory=set)
    admin_pools: set[int] = Field(default_factory=set)
    edit_pools: set[int] = Field(default_factory=set)
