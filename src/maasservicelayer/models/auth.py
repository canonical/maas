# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import BaseModel, Field


class RBACPermissionsPools(BaseModel):
    """
    Represents the resource pool permissions for a specific user in a Role-Based Access Control (RBAC) system.

    This class holds sets of resource pool IDs corresponding to various permission levels for a user.
    Each permission property is either:
    - `None`: If the permission set was not requested from RBAC.
    - An empty set: If the user does not have any resource pools for the specific permission.
    - A set of pool IDs: If the user has permissions for those specific resource pools.

    visible_pools (set[int] | None): pools where the user can see machines either unowned or owned by themselves
    view_all_pools (set[int] | None): pools where the user can see all machines even if the machine is owned by a different
    user
    deploy_pools (set[int] | None): pools where the user can deploy machines
    admin_pools (set[int] | None): pools where the user can admin machines
    edit_pools (set[int] | None): pools that the user can edit
    """

    visible_pools: set[int] | None = Field(default=None)
    view_all_pools: set[int] | None = Field(default=None)
    deploy_pools: set[int] | None = Field(default=None)
    admin_pools: set[int] | None = Field(default=None)
    edit_pools: set[int] | None = Field(default=None)
    can_edit_all_resource_pools: bool | None = Field(default=None)


class AuthenticatedUser(BaseModel):
    """Represents the currently logged-in user with their permissions.

    Attributes:
        id (int): the user ID
        username (str): the username of the user
        rbac_permissions (RBACPermissionsPools | None): Contains the RBAC permissions for the user if RBAC
            is enabled. If RBAC is disabled, this attribute is set to `None`.
    """

    id: int
    username: str
    rbac_permissions: RBACPermissionsPools | None = Field(default=None)
