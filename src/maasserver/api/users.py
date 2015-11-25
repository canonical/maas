# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `User`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'UserHandler',
    'UsersHandler',
    ]


from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from maasserver.api.support import (
    admin_method,
    OperationsHandler,
)
from maasserver.api.utils import (
    extract_bool,
    get_mandatory_param,
)
from maasserver.models import User
from maasserver.utils.orm import get_one
from piston3.models import Consumer
from piston3.utils import rc


class UsersHandler(OperationsHandler):
    """Manage the user accounts of this MAAS."""
    api_doc_section_name = "Users"
    update = delete = None

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('users_handler', [])

    def read(self, request):
        """List users."""
        return User.objects.all().order_by('username')

    @admin_method
    def create(self, request):
        """Create a MAAS user account.

        This is not safe: the password is sent in plaintext.  Avoid it for
        production, unless you are confident that you can prevent eavesdroppers
        from observing the request.

        :param username: Identifier-style username for the new user.
        :type username: unicode
        :param email: Email address for the new user.
        :type email: unicode
        :param password: Password for the new user.
        :type password: unicode
        :param is_superuser: Whether the new user is to be an administrator.
        :type is_superuser: bool ('0' for False, '1' for True)

        Returns 400 if any mandatory parameters are missing.
        """
        username = get_mandatory_param(request.data, 'username')
        email = get_mandatory_param(request.data, 'email')
        password = get_mandatory_param(request.data, 'password')
        is_superuser = extract_bool(
            get_mandatory_param(request.data, 'is_superuser'))

        if is_superuser:
            return User.objects.create_superuser(
                username=username, password=password, email=email)
        else:
            return User.objects.create_user(
                username=username, password=password, email=email)


class UserHandler(OperationsHandler):
    """Manage a user account."""
    api_doc_section_name = "User"
    create = update = None

    model = User
    fields = (
        'username',
        'email',
        'is_superuser',
        )

    def read(self, request, username):
        return get_object_or_404(User, username=username)

    @admin_method
    def delete(self, request, username):
        """Deletes a user"""
        if request.user.username == username:
            raise ValidationError("An administrator cannot self-delete.")

        user = get_one(User.objects.filter(username=username))

        if user is not None:
            if user.node_set.exists():
                raise ValidationError(
                    "A user with assigned nodes cannot be deleted.")
            elif user.staticipaddress_set.exists():
                raise ValidationError(
                    "A user with reserved IP addresses cannot be deleted.")
            else:
                Consumer.objects.filter(user=user).delete()
                user.delete()

        return rc.DELETED
