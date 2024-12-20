#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from pydantic import BaseModel, Field

from maasservicelayer.auth.jwt import UserRole


class RBACPermissionsPools(BaseModel):
    """
    Represents the resource pool permissions for a specific user in a Role-Based Access Control (RBAC) system.

    This class holds sets of resource pool IDs corresponding to various permission levels for a user.
    Each permission property is either:
    - `None`: If the permission set was not requested from RBAC.
    - An empty set: If the user does not have any resource pools for the specific permission.
    - A set of pool IDs: If the user has permissions for those specific resource pools.

    visible_pools (Optional[set[int]]): pools where the user can see machines either unowned or owned by themselves
    view_all_pools (Optional[set[int]]): pools where the user can see all machines even if the machine is owned by a different
    user
    deploy_pools (Optional[set[int]]): pools where the user can deploy machines
    admin_pools (Optional[set[int]]): pools where the user can admin machines
    edit_pools (Optional[set[int]]): pools that the user can edit
    """

    visible_pools: Optional[set[int]] = Field(default=None)
    view_all_pools: Optional[set[int]] = Field(default=None)
    deploy_pools: Optional[set[int]] = Field(default=None)
    admin_pools: Optional[set[int]] = Field(default=None)
    edit_pools: Optional[set[int]] = Field(default=None)
    can_edit_all_resource_pools: Optional[bool] = Field(default=None)


class AuthenticatedUser(BaseModel):
    """Represents the currently logged-in user with their permissions.

    Attributes:
        id (int): the user ID
        username (str): the username of the user
        roles (UserRole): local roles that the user has, i.e. user or admin
        rbac_permissions (Optional[RBACPermissionsPools]): Contains the RBAC permissions for the user if RBAC
            is enabled. If RBAC is disabled, this attribute is set to `None`.
    """

    id: int
    username: str
    roles: set[UserRole]
    rbac_permissions: Optional[RBACPermissionsPools] = Field(default=None)

    def is_admin(self) -> bool:
        return UserRole.ADMIN in self.roles
