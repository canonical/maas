# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `UserGroup`."""

from piston3.utils import rc

from maasserver.api.support import (
    check_permission,
    operation,
    OperationsHandler,
)
from maasserver.exceptions import (
    MAASAPIBadRequest,
    MAASAPINotFound,
    UserAlreadyGroupMemberConflict,
)
from maasserver.sqlalchemy import service_layer
from maasservicelayer.builders.usergroups import UserGroupBuilder
from maasservicelayer.services.usergroups import (
    UserAlreadyInGroup,
    UserGroupNotFound,
)

DISPLAYED_USERGROUP_FIELDS = ("id", "name", "description")


class UserGroupHandler(OperationsHandler):
    """Manage a user group."""

    api_doc_section_name = "UserGroup"
    create = None

    @classmethod
    def resource_uri(cls, usergroup=None):
        group_id = "id"
        if usergroup is not None:
            group_id = (
                usergroup["id"]
                if isinstance(usergroup, dict)
                else usergroup.id
            )
        return ("usergroup_handler", [group_id])

    @check_permission("can_view_identities")
    def read(self, request, id):
        """@description Returns a user group.
        @param (url-string) "{id}" [required=true] A group ID.

        @success (http-status-code) "server_success" 200
        @success (json) "content_success" A JSON object containing group
            information.

        @error (http-status-code) "404" 404
        @error (content) "notfound" The group is not found.
        """
        group = service_layer.services.usergroups.get_by_id(int(id))
        if group is None:
            raise MAASAPINotFound(f"UserGroup with id {id} not found.")
        return {
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "resource_uri": f"/MAAS/api/2.0/groups/{group.id}/",
        }

    @check_permission("can_edit_identities")
    def update(self, request, id):
        """@description Updates a user group.
        @param (url-string) "{id}" [required=true] A group ID.
        @param (string) "name" [required=false] The group name.
        @param (string) "description" [required=false] The group description.

        @success (http-status-code) "server_success" 200

        @error (http-status-code) "404" 404
        @error (content) "notfound" The group is not found.
        """
        group = service_layer.services.usergroups.get_by_id(int(id))
        if group is None:
            raise MAASAPINotFound(f"UserGroup with id {id} not found.")

        builder = UserGroupBuilder()
        if "name" in request.data:
            builder.name = request.data["name"]
        if "description" in request.data:
            builder.description = request.data["description"]

        updated = service_layer.services.usergroups.update_by_id(
            int(id), builder
        )
        return {
            "id": updated.id,
            "name": updated.name,
            "description": updated.description,
            "resource_uri": f"/MAAS/api/2.0/groups/{updated.id}/",
        }

    @check_permission("can_edit_identities")
    def delete(self, request, id):
        """@description Deletes a user group.
        @param (url-string) "{id}" [required=true] A group ID.

        @success (http-status-code) "server_success" 204
        """
        group = service_layer.services.usergroups.get_by_id(int(id))
        if group is None:
            raise MAASAPINotFound(f"UserGroup with id {id} not found.")
        service_layer.services.usergroups.delete_by_id(int(id))
        return rc.DELETED

    @operation(idempotent=True)
    @check_permission("can_view_identities")
    def list_members(self, request, id):
        """@description Lists members of a user group.
        @param (url-string) "{id}" [required=true] A group ID.

        @success (http-status-code) "server_success" 200
        @success (json) "content_success" A JSON list of group members.

        @error (http-status-code) "404" 404
        @error (content) "notfound" The group is not found.
        """
        group = service_layer.services.usergroups.get_by_id(int(id))
        if group is None:
            raise MAASAPINotFound(f"UserGroup with id {id} not found.")

        members = service_layer.services.usergroups.list_usergroup_members(
            int(id)
        )
        return [
            {
                "username": member.username,
                "email": member.email,
            }
            for member in members
        ]

    @operation(idempotent=False)
    @check_permission("can_edit_identities")
    def add_member(self, request, id):
        """@description Adds a user to a user group.
        @param (url-string) "{id}" [required=true] A group ID.
        @param (string) "username" [required=true] The username to add.

        @success (http-status-code) "server_success" 200

        @error (http-status-code) "400" 400
        @error (content) "badrequest" username is required.
        @error (http-status-code) "404" 404
        @error (content) "notfound" The group or user is not found.
        @error (http-status-code) "409" 409
        @error (content) "conflict" The user is already a member of the group.

        """
        username = request.data.get("username")
        if not username:
            raise MAASAPIBadRequest("username is required.")

        user = service_layer.services.users.get_by_username(username)
        if user is None:
            raise MAASAPINotFound(f"User '{username}' not found.")

        try:
            service_layer.services.usergroups.add_user_to_group_by_id(
                user.id, int(id)
            )
        except UserGroupNotFound as err:
            raise MAASAPINotFound(
                f"UserGroup with id {id} not found."
            ) from err
        except UserAlreadyInGroup as err:
            raise UserAlreadyGroupMemberConflict(
                f"User `{user.username}` is already a member of the group with ID `{id}`."
            ) from err

        return rc.ALL_OK

    @operation(idempotent=False)
    @check_permission("can_edit_identities")
    def remove_member(self, request, id):
        """@description Removes a user from a user group.
        @param (url-string) "{id}" [required=true] A group ID.
        @param (string) "username" [required=true] The username to remove.

        @success (http-status-code) "server_success" 204

        @error (http-status-code) "400" 400
        @error (content) "badrequest" username is required.
        @error (http-status-code) "404" 404
        @error (content) "notfound" The user is not found.
        """
        username = request.data.get("username")
        if not username:
            raise MAASAPIBadRequest("username is required.")

        group = service_layer.services.usergroups.get_by_id(int(id))
        if group is None:
            raise MAASAPINotFound(f"UserGroup with id {id} not found.")

        user = service_layer.services.users.get_by_username(username)
        if user is None:
            raise MAASAPINotFound(f"User '{username}' not found.")

        service_layer.services.usergroups.remove_user_from_group(
            int(id), user.id
        )
        return rc.DELETED


class UserGroupsHandler(OperationsHandler):
    """Manage user groups."""

    api_doc_section_name = "UserGroups"
    update = delete = None

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("usergroups_handler", [])

    @check_permission("can_edit_identities")
    def create(self, request):
        """@description Creates a new user group.
        @param (string) "name" [required=true] The group name.
        @param (string) "description" [required=false] The group description.

        @success (http-status-code) "server_success" 200

        @error (http-status-code) "400" 400
        @error (content) "badrequest" Name is required.
        """
        name = request.data.get("name")
        if not name:
            raise MAASAPIBadRequest("Name is required.")
        description = request.data.get("description", "")

        builder = UserGroupBuilder(name=name, description=description)
        group = service_layer.services.usergroups.create(builder)
        return {
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "resource_uri": f"/MAAS/api/2.0/groups/{group.id}/",
        }

    @check_permission("can_view_identities")
    def read(self, request):
        """@description Lists all user groups.

        @success (http-status-code) "server_success" 200
        """
        result = service_layer.services.usergroups.list_all()
        return [
            {
                "id": group.id,
                "name": group.name,
                "description": group.description,
                "resource_uri": f"/MAAS/api/2.0/groups/{group.id}/",
            }
            for group in result
        ]
