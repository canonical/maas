# Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The user handler for the WebSocket connection."""

__all__ = [
    "UserHandler",
]

from django.contrib.auth.models import User
from django.db.models import Count
from django.http import HttpRequest
from maasserver.audit import create_audit_event
from maasserver.enum import ENDPOINT
from maasserver.models.user import SYSTEM_USERS
from maasserver.permissions import (
    NodePermission,
    PodPermission,
    ResourcePoolPermission,
)
from maasserver.websockets.base import (
    Handler,
    HandlerDoesNotExistError,
)
from provisioningserver.events import EVENT_TYPES


class UserHandler(Handler):

    class Meta:
        queryset = User.objects.filter(is_active=True).annotate(
            sshkeys_count=Count('sshkey'))
        pk = 'id'
        allowed_methods = [
            'list',
            'get',
            'auth_user',
            'mark_intro_complete',
            'create_authorisation_token',
            'delete_authorisation_token',
        ]
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "is_superuser",
            "sshkeys_count",
        ]
        listen_channels = [
            "user",
        ]

    def get_queryset(self, for_list=False):
        """Return `QuerySet` for users only viewable by `user`."""
        users = super(UserHandler, self).get_queryset(for_list=for_list)
        if self.user.is_superuser:
            # Super users can view all users, except for the built-in users
            return users.exclude(username__in=SYSTEM_USERS)
        else:
            # Standard users can only view their self. We filter by username
            # so a queryset is still returned instead of just a list with
            # only the user in it.
            return users.filter(username=self.user.username)

    def get_object(self, params):
        """Get object by using the `pk` in `params`."""
        obj = super(UserHandler, self).get_object(params)
        if self.user.is_superuser:
            # Super user can get any user.
            return obj
        elif obj == self.user:
            # Standard user can only get self.
            return obj
        else:
            raise HandlerDoesNotExistError(params[self._meta.pk])

    def dehydrate(self, obj, data, for_list=False):
        data["sshkeys_count"] = obj.sshkeys_count
        if obj.id == self.user.id:
            # User is reading information about itself, so provide the global
            # permissions.
            data['global_permissions'] = self._get_global_permissions()
        return data

    def _get_global_permissions(self):
        """Return the global permissions the user can perform."""
        permissions = []
        if self.user.has_perm(NodePermission.admin):
            permissions.append('machine_create')
        if self.user.has_perm(NodePermission.view):
            permissions.append('device_create')
        if self.user.has_perm(ResourcePoolPermission.create):
            permissions.append('resource_pool_create')
        if self.user.has_perm(ResourcePoolPermission.delete):
            permissions.append('resource_pool_delete')
        if self.user.has_perm(PodPermission.create):
            permissions.append('pod_create')
        return permissions

    def auth_user(self, params):
        """Return the authenticated user."""
        self.user.sshkeys_count = self.user.sshkey_set.count()
        return self.full_dehydrate(self.user)

    def mark_intro_complete(self, params):
        """Mark the user as completed the intro.

        This is only for the authenticated user. This cannot be performed on
        a different user.
        """
        self.user.userprofile.completed_intro = True
        self.user.userprofile.save()
        return self.full_dehydrate(self.user)

    def create_authorisation_token(self, params):
        """Create an authorisation token for the user.

        This is only for the authenticated user. This cannot be performed on
        a different user.
        """
        request = HttpRequest()
        request.user = self.user
        profile = self.user.userprofile
        consumer, token = profile.create_authorisation_token()
        create_audit_event(
            EVENT_TYPES.AUTHORISATION, ENDPOINT.UI,
            request, None, "Created token.")
        return {
            'key': token.key,
            'secret': token.secret,
            'consumer': {
                'key': consumer.key,
                'name': consumer.name,
            },
        }

    def delete_authorisation_token(self, params):
        """Delete an authorisation token for the user.

        This is only for the authenticated user. This cannot be performed on
        a different user.
        """
        request = HttpRequest()
        request.user = self.user
        profile = self.user.userprofile
        profile.delete_authorisation_token(params['key'])
        create_audit_event(
            EVENT_TYPES.AUTHORISATION, ENDPOINT.UI,
            request, None, "Deleted token.")
        return {}
