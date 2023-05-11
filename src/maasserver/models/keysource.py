# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

""":class:`KeySource` and friends."""

from typing import TYPE_CHECKING

from django.db.models import BooleanField, CharField, Manager

from maasserver.enum import KEYS_PROTOCOL_TYPE_CHOICES
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.keys import get_protocol_keys

if TYPE_CHECKING:
    from django.contrib.auth.models import User


class KeySourceManager(Manager):
    """A utility to manage the colletion of `KeySource`s."""

    def save_keys_for_user(self, user: "User", protocol: str, auth_id: str):
        """Save SSH Keys for user's protocol and auth_id.

        :param user: The user to save the SSH keys for.
        :param protocol: The protocol 'source'.
        :param auth_id: The protocol username.
        :return: List of saved `SSHKey`s.
        """
        source, _ = self.get_or_create(protocol=protocol, auth_id=auth_id)
        return source.import_keys(user)


class KeySource(CleanSave, TimestampedModel):
    """A `KeySource` represents the source where an SSH public key comes from.

    Users will be able to access allocated nodes using any of their
    registered keys.

    :ivar protocol: The protocol 'source'.
    :ivar auth_id: The protocol username.
    :ivar auto_update: An optional flag to indicate if this KeySource should
        periodically update its keys.
    """

    objects = KeySourceManager()

    protocol = CharField(
        max_length=64,
        null=False,
        editable=True,
        choices=KEYS_PROTOCOL_TYPE_CHOICES,
    )

    auth_id = CharField(max_length=255, null=False, editable=True)

    # Whether keys from this source should be automatically updated
    # XXX auto-update not implemented yet
    auto_update = BooleanField(default=False)

    class Meta:
        verbose_name = "Key Source"

    def __str__(self):
        return f"{self.protocol}:{self.auth_id}"

    def import_keys(self, user: "User"):
        """Save SSH keys."""
        # Avoid circular imports.
        from maasserver.models.sshkey import SSHKey

        keys = get_protocol_keys(self.protocol, self.auth_id)
        return [
            SSHKey.objects.get_or_create(key=key, user=user, keysource=self)[0]
            for key in keys
        ]
