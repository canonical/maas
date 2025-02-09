# Copyright 2014-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `User`."""

from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from piston3.handler import BaseHandler
from piston3.models import Consumer
from piston3.utils import rc

from maasserver.api.ssh_keys import SSHKeysHandler
from maasserver.api.support import admin_method, operation, OperationsHandler
from maasserver.api.utils import extract_bool, get_mandatory_param
from maasserver.audit import create_audit_event
from maasserver.enum import ENDPOINT
from maasserver.exceptions import (
    CannotDeleteUserException,
    MAASAPIValidationError,
)
from maasserver.forms import DeleteUserForm
from maasserver.models import User, UserProfile
from maasserver.models.user import SYSTEM_USERS
from maasserver.utils.orm import get_one
from provisioningserver.events import EVENT_TYPES


class UsersHandler(OperationsHandler):
    """Manage the user accounts of this MAAS."""

    api_doc_section_name = "Users"
    update = delete = None

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("users_handler", [])

    def read(self, request):
        """@description-title List users
        @description List users

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing a list of
        users.
        @success-example "success-json" [exkey=list] placeholder text
        """
        return User.objects.all().order_by("username")

    @operation(idempotent=True)
    def whoami(self, request):
        """@description-title Retrieve logged-in user
        @description Returns the currently logged-in user.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing information
        about the currently logged-in user.
        @success-example "success-json" [exkey=whoami] placeholder text
        """
        return request.user

    @admin_method
    def create(self, request):
        """@description-title Create a MAAS user account
        @description Creates a MAAS user account.

        This is not safe: the password is sent in plaintext.  Avoid it for
        production, unless you are confident that you can prevent eavesdroppers
        from observing the request.

        @param (string) "username" [required=true] Identifier-style username
        for the new user.

        @param (string) "email" [required=true] Email address for the new user.

        @param (string) "password" [required=true] Password for the new user.

        @param (boolean) "is_superuser" [required=true] Whether the new user is
        to be an administrator. ('0' == False, '1' == True)

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing information
        about the new user.
        @success-example "success-json" [exkey=create] placeholder text

        @error (http-status-code) "400" 400
        @error (content) "error-content" Mandatory parameters are missing.
        @error-example "error-content"
            No provided username!
        """
        username = get_mandatory_param(request.data, "username")
        email = get_mandatory_param(request.data, "email")
        if request.external_auth_info:
            password = request.data.get("password")
        else:
            password = get_mandatory_param(request.data, "password")
        is_superuser = extract_bool(
            get_mandatory_param(request.data, "is_superuser")
        )

        create_audit_event(
            EVENT_TYPES.AUTHORISATION,
            ENDPOINT.API,
            request,
            None,
            description=(
                "Created %s '%s'."
                % ("admin" if is_superuser else "user", username)
            ),
        )
        if is_superuser:
            user = User.objects.create_superuser(
                username=username, password=password, email=email
            )
            if request.data.get("key") is not None:
                request.user = user
                sshkeys_handler = SSHKeysHandler()
                sshkeys_handler.create(request)
            return user
        else:
            return User.objects.create_user(
                username=username, password=password, email=email
            )


class UserHandler(OperationsHandler):
    """Manage a user account."""

    api_doc_section_name = "User"
    create = update = None

    model = User
    fields = ("username", "email", "is_local", "is_superuser")

    def read(self, request, username):
        """@description-title Retrieve user details
        @description Retrieve a user's details.

        @param (string) "{username}" [required=true] A username.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing user
        information.
        @success-example "success-json" [exkey=read] placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The given user was not found.
        @error-example "not-found"
            No User matches the given query.
        """
        return get_object_or_404(User, username=username)

    @admin_method
    def delete(self, request, username):
        """@description-title Delete a user
        @description Deletes a given username.

        @param (string) "{username}" [required=true] The username to delete.

        @param (string) "transfer_resources_to" [required=false] An optional
        username. If supplied, the allocated resources of the user being
        deleted will be transferred to this user. A user can't be removed
        unless its resources (machines, IP addresses, ...), are released or
        transfered to another user.

        @success (http-status-code) "204" 204
        """
        if request.user.username == username:
            raise ValidationError("An administrator cannot self-delete.")

        form = DeleteUserForm(data=request.GET)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)

        user = get_one(User.objects.filter(username=username))
        if user is not None:
            new_owner_username = form.cleaned_data["transfer_resources_to"]
            if new_owner_username:
                new_owner = get_object_or_404(
                    User, username=new_owner_username
                )
                if new_owner is not None:
                    user.userprofile.transfer_resources(new_owner)

            Consumer.objects.filter(user=user).delete()
            try:
                user.userprofile.delete()
                create_audit_event(
                    EVENT_TYPES.AUTHORISATION,
                    ENDPOINT.API,
                    request,
                    None,
                    description=(
                        "Deleted %s '%s'."
                        % ("admin" if user.is_superuser else "user", username)
                    ),
                )
            except CannotDeleteUserException as e:
                raise ValidationError(str(e))  # noqa: B904

        return rc.DELETED

    @classmethod
    def resource_uri(cls, user=None):
        username = "username" if user is None else user.username
        return ("user_handler", [username])

    @classmethod
    def is_local(self, user=None):
        if not user:
            return False
        if user.username in SYSTEM_USERS:
            return True

        return user.userprofile.is_local


class UserProfileHandler(BaseHandler):
    """Empty handler for UserProfile.

    This is defined to avoid circular references when serializing User objects,
    since the UserProfile references the user in turn.

    """

    model = UserProfile
    exclude = ("user",)
