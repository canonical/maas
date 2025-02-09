# Copyright 2015-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The user handler for the WebSocket connection."""

from django.contrib.auth.forms import (
    AdminPasswordChangeForm,
    PasswordChangeForm,
)
from django.contrib.auth.models import User
from django.db.models import Count
from django.http import HttpRequest

from maasserver.audit import create_audit_event
from maasserver.enum import ENDPOINT
from maasserver.forms import EditUserForm, NewUserCreationForm
from maasserver.models.user import SYSTEM_USERS
from maasserver.permissions import (
    NodePermission,
    PodPermission,
    ResourcePoolPermission,
)
from maasserver.utils.forms import get_QueryDict
from maasserver.websockets.base import (
    dehydrate_datetime,
    Handler,
    HandlerDoesNotExistError,
    HandlerPermissionError,
    HandlerValidationError,
)
from provisioningserver.events import EVENT_TYPES


class UserHandler(Handler):
    class Meta:
        queryset = (
            User.objects.filter(is_active=True)
            .annotate(
                sshkeys_count=Count("sshkey", distinct=True),
                machines_count=Count("node", distinct=True),
            )
            .select_related("userprofile")
        )
        form_requires_request = False
        pk = "id"
        allowed_methods = [
            "create",
            "delete",
            "list",
            "get",
            "update",
            "auth_user",
            "mark_intro_complete",
            "change_password",
            "admin_change_password",
        ]
        fields = [
            "id",
            "username",
            "last_name",
            "email",
            "is_superuser",
            "sshkeys_count",
            "last_login",
            "is_local",
            "machines_count",
            "completed_intro",
        ]
        listen_channels = ["user"]

    def get_queryset(self, for_list=False):
        """Return `QuerySet` for users only viewable by `user`."""
        users = super().get_queryset(for_list=for_list)
        if self.user.is_superuser:
            # Super users can view all users, except for the built-in users
            return users.exclude(username__in=SYSTEM_USERS)
        else:
            # Standard users can only view their self. We filter by username
            # so a queryset is still returned instead of just a list with
            # only the user in it.
            return users.filter(username=self.user.username)

    def get_object(self, params, permission=None):
        """Get object by using the `pk` in `params`."""
        obj = super().get_object(params, permission=permission)
        if self.user.is_superuser:
            # Super user can get any user.
            return obj
        elif obj == self.user:
            # Standard user can only get self.
            return obj
        else:
            # For security reasons, message must be identical to the one in Handler.get_object
            raise HandlerDoesNotExistError(
                f"Object with id ({params[self._meta.pk]}) does not exist"
            )

    def get_form_class(self, action):
        """Pick the right form for the given action."""
        forms = {"create": NewUserCreationForm, "update": EditUserForm}
        return forms.get(action)

    def create_audit_event(self, event_type, description):
        """Create an audit event for this user"""
        request = HttpRequest()
        request.user = self.user
        return create_audit_event(
            event_type, ENDPOINT.UI, request, None, description
        )

    def create(self, params):
        """Create a new user, and log an event for it."""
        try:
            result = super().create(params=params)
        except HandlerDoesNotExistError:
            raise HandlerPermissionError()  # noqa: B904
        self.create_audit_event(
            EVENT_TYPES.AUTHORISATION,
            "Created {} '{}'.".format(
                "admin" if params["is_superuser"] else "user",
                params["username"],
            ),
        )
        return result

    def update(self, params):
        """Update a user, and log an event for it."""
        try:
            result = super().update(params=params)
        except HandlerDoesNotExistError:
            raise HandlerPermissionError()  # noqa: B904
        self.create_audit_event(
            EVENT_TYPES.AUTHORISATION,
            (
                "Updated user profile (username: {username}, "
                "full name: {last_name}, "
                "email: {email}, administrator: {is_superuser})"
            ).format(**params),
        )
        return result

    def delete(self, params):
        """Delete a user, and log an event for it."""
        try:
            user = self.get_object(
                params, permission=self._meta.delete_permission
            )
            self.create_audit_event(
                EVENT_TYPES.AUTHORISATION,
                "Deleted {} '{}'.".format(
                    "admin" if user.is_superuser else "user", user.username
                ),
            )
            result = super().delete(params=params)
        except HandlerDoesNotExistError:
            raise HandlerPermissionError()  # noqa: B904
        return result

    def dehydrate(self, obj, data, for_list=False):
        data.update(
            {
                "sshkeys_count": obj.sshkeys_count,
                "is_local": obj.userprofile.is_local,
                "completed_intro": obj.userprofile.completed_intro,
                "machines_count": obj.machines_count,
                "last_login": dehydrate_datetime(obj.last_login),
            }
        )
        if obj.id == self.user.id:
            # User is reading information about itself, so provide the global
            # permissions.
            data["global_permissions"] = self._get_global_permissions()
        return data

    def _get_global_permissions(self):
        """Return the global permissions the user can perform."""
        permissions = []
        if self.user.has_perm(NodePermission.admin):
            permissions.append("machine_create")
        if self.user.has_perm(NodePermission.view):
            permissions.append("device_create")
        if self.user.has_perm(ResourcePoolPermission.create):
            permissions.append("resource_pool_create")
        if self.user.has_perm(ResourcePoolPermission.delete):
            permissions.append("resource_pool_delete")
        if self.user.has_perm(PodPermission.create):
            permissions.append("pod_create")
        return permissions

    def auth_user(self, params):
        """Return the authenticated user."""
        return self.full_dehydrate(
            self.get_object(params={"id": self.user.id})
        )

    def mark_intro_complete(self, params):
        """Mark the user as completed the intro.

        This is only for the authenticated user. This cannot be performed on
        a different user.
        """
        user = self.get_object(params={"id": self.user.id})
        user.userprofile.completed_intro = True
        user.userprofile.save()
        return self.full_dehydrate(user)

    def change_password(self, params):
        """Update the authenticated user password."""
        user = self.get_object(params={"id": self.user.id})
        form = PasswordChangeForm(user=user, data=get_QueryDict(params))
        if form.is_valid():
            form.save()
            return self.full_dehydrate(user)
        else:
            raise HandlerValidationError(form.errors)

    def admin_change_password(self, params):
        """As Admin, update another user's password."""
        if not self.user.is_superuser:
            raise HandlerPermissionError()
        user = self.get_object(params)
        form = AdminPasswordChangeForm(user=user, data=get_QueryDict(params))
        if form.is_valid():
            form.save()
        else:
            raise HandlerValidationError(form.errors)
