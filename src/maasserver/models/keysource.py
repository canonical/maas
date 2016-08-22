# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

""":class:`KeySource` and friends."""

__all__ = [
    'KeySource',
    ]

from django.db.models import (
    BooleanField,
    CharField,
    Manager,
)
from maasserver import DefaultMeta
from maasserver.enum import KEYS_PROTOCOL_TYPE_CHOICES
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.keys import get_protocol_keys


class KeySourceManager(Manager):
    """A utility to manage the colletion of `KeySource`s."""

    def save_keys_for_user(self, user, protocol, auth_id):
        source = self.create(protocol=protocol, auth_id=auth_id)
        source.import_keys(user)
        return source


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
        max_length=64, null=False, editable=True,
        choices=KEYS_PROTOCOL_TYPE_CHOICES)

    auth_id = CharField(max_length=255, null=False, editable=True)

    auto_update = BooleanField(default=False)

    class Meta(DefaultMeta):
        verbose_name = "Key Source"

    def __str__(self):
        return self.protocol

    def import_keys(self, user):
        """Save SSH keys."""
        # Avoid circular imports.
        from maasserver.models.sshkey import SSHKey

        keys = get_protocol_keys(self.protocol, self.auth_id)
        for key in keys:
            SSHKey.objects.create(key=key, user=user, keysource=self)
