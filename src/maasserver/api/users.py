# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `User`."""

__all__ = [
    'UserHandler',
    'UsersHandler',
    ]


from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from maasserver.api.support import (
    admin_method,
    operation,
    OperationsHandler,
)
from maasserver.api.utils import (
    extract_bool,
    get_mandatory_param,
)
from maasserver.audit import create_audit_event
from maasserver.enum import ENDPOINT
from maasserver.exceptions import (
    CannotDeleteUserException,
    MAASAPIValidationError,
)
from maasserver.forms import DeleteUserForm
from maasserver.models import User
from maasserver.utils.orm import get_one
from piston3.models import Consumer
from piston3.utils import rc
from provisioningserver.events import EVENT_TYPES


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

    @operation(idempotent=True)
    def whoami(self, request):
        """Returns the currently logged in user."""
        return request.user

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

        create_audit_event(
            EVENT_TYPES.AUTHORISATION, ENDPOINT.API, request, None,
            description=(
                "%s %s" % ('Admin' if is_superuser else 'User', username) +
                " created by '%(username)s'."))
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

        form = DeleteUserForm(data=request.GET)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)

        user = get_one(User.objects.filter(username=username))
        if user is not None:
            new_owner_username = form.cleaned_data['transfer_resources_to']
            if new_owner_username:
                new_owner = get_object_or_404(
                    User, username=new_owner_username)
                if new_owner is not None:
                    user.userprofile.transfer_resources(new_owner)

            Consumer.objects.filter(user=user).delete()
            try:
                user.userprofile.delete()
                create_audit_event(
                    EVENT_TYPES.AUTHORISATION, ENDPOINT.API, request, None,
                    description=(
                        "%s %s" % (
                            'Admin' if user.is_superuser else 'User',
                            username) + " deleted by '%(username)s'."))
            except CannotDeleteUserException as e:
                raise ValidationError(str(e))

        return rc.DELETED

    @classmethod
    def resource_uri(cls, user=None):
        username = "username" if user is None else user.username
        return ('user_handler', [username])
