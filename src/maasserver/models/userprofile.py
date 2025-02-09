# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""UserProfile model."""

from django.contrib.auth.models import User
from django.db.models import (
    BooleanField,
    CASCADE,
    DateTimeField,
    Manager,
    Model,
    OneToOneField,
)
from django.shortcuts import get_object_or_404
from piston3.models import Token

from maasserver.exceptions import CannotDeleteUserException
from maasserver.models.cleansave import CleanSave


class UserProfileManager(Manager):
    """A utility to manage the collection of `UserProfile` (or `User`).

    Use this when dealing with users that represent real-world users.  System
    users do not have `UserProfile` objects attached to them.
    """

    def all_users(self):
        """Returns all "real" users (i.e. not including system users).

        :return: A QuerySet of the users.
        :rtype: django.db.models.query.QuerySet_

        .. _django.db.models.query.QuerySet: https://docs.djangoproject.com/
           en/dev/ref/models/querysets/

        """
        user_ids = UserProfile.objects.all().values_list("user", flat=True)
        return User.objects.filter(id__in=user_ids)


class UserProfile(CleanSave, Model):
    """A User profile to store MAAS specific methods and fields.

    :ivar user: The related User_.

    .. _User: https://docs.djangoproject.com/
       en/dev/topics/auth/
       #storing-additional-information-about-users

    """

    objects = UserProfileManager()
    user = OneToOneField(User, on_delete=CASCADE)

    # Set to true when the user has completed the intro page of the Web UI.
    completed_intro = BooleanField(default=False)
    # Last time the user was chacked with the external authentication source
    auth_last_check = DateTimeField(blank=True, null=True)
    # Whether the user is local or comes from the external authentication
    # source
    is_local = BooleanField(default=True)

    def delete(self):
        # check owned resources
        owned_resources = [
            ("staticipaddress", "static IP address(es)"),
            ("iprange", "IP range(s)"),
            ("node", "node(s)"),
        ]
        messages = []
        for attr, title in owned_resources:
            count = getattr(self.user, attr + "_set").count()
            if count:
                messages.append(f"{count} {title}")

        if messages:
            raise CannotDeleteUserException(
                "User {} cannot be deleted: {} are still allocated".format(
                    self.user.username, ", ".join(messages)
                )
            )

        if self.user.filestorage_set.exists():
            self.user.filestorage_set.all().delete()
        self.user.consumers.all().delete()
        self.user.delete()
        super().delete()

    def transfer_resources(self, new_owner):
        """Transfer owned resources to another user.

        Nodes, static IP addresses and IP ranges owned by the user are
        transfered to the new owner.

        :param new_owner: the UserProfile to transfer ownership to.
        :type new_owner: maasserver.models.UserProfile

        """
        self.user.node_set.update(owner=new_owner)
        self.user.staticipaddress_set.update(user=new_owner)
        self.user.iprange_set.update(user=new_owner)

    def get_authorisation_tokens(self):
        """Fetches all the user's OAuth tokens.

        :return: A QuerySet of the tokens.
        :rtype: django.db.models.query.QuerySet_

        .. _django.db.models.query.QuerySet: https://docs.djangoproject.com/
           en/dev/ref/models/querysets/

        """
        # Avoid circular imports.
        from maasserver.models.user import get_auth_tokens

        return get_auth_tokens(self.user)

    def create_authorisation_token(self, consumer_name=None):
        """Create a new Token and its related Consumer (OAuth authorisation).

        :return: A tuple containing the Consumer and the Token that were
            created.
        :rtype: tuple

        """
        # Avoid circular imports.
        from maasserver.models.user import create_auth_token

        token = create_auth_token(self.user, consumer_name)
        return token.consumer, token

    def delete_authorisation_token(self, token_key):
        """Delete the user's OAuth token wich key token_key.

        :param token_key: The key of the token to be deleted.
        :type token_key: string
        :raises: `django.http.Http404`

        """
        token = get_object_or_404(
            Token, user=self.user, token_type=Token.ACCESS, key=token_key
        )
        token.consumer.delete()
        token.delete()

    def modify_consumer_name(self, token_key, consumer_name):
        """Modify consumer name of an existing token key.

        :param token_key: The key of the token to be deleted.
        :type token_key: string
        :param consumer_name: Name of the token consumer.
        :type consumer_name: string
        :raises: `django.http.Http404`
        """
        token = get_object_or_404(
            Token, user=self.user, token_type=Token.ACCESS, key=token_key
        )
        token.consumer.name = consumer_name
        token.consumer.save()
        token.save()

    def __str__(self):
        return self.user.username
