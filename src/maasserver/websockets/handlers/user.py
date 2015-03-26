# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The user handler for the WebSocket connection."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "UserHandler",
    ]

from django.contrib.auth.models import User
from maasserver.models.user import SYSTEM_USERS
from maasserver.websockets.base import (
    Handler,
    HandlerDoesNotExistError,
)


class UserHandler(Handler):

    class Meta:
        queryset = User.objects.filter(is_active=True)
        pk = 'id'
        allowed_methods = ['list', 'get', 'auth_user']
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "is_superuser",
            ]
        listen_channels = [
            "user",
            ]

    def get_queryset(self):
        """Return `QuerySet` for users only viewable by `user`."""
        users = super(UserHandler, self).get_queryset()
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

    def auth_user(self, params):
        """Return the authenticated user."""
        return self.full_dehydrate(self.user)
