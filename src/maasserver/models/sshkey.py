# Copyright 2012-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

""":class:`SSHKey` and friends."""

from typing import List

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import CASCADE, CharField, ForeignKey, Manager, TextField

from maasserver.enum import KEYS_PROTOCOL_TYPE_CHOICES
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.sqlalchemy import service_layer
from maasservicelayer.exceptions.catalog import ValidationException
from maasservicelayer.models.sshkeys import SshKey


class OpenSSHKeyError(ValueError):
    """The given key was not recognised or was corrupt."""


class ImportSSHKeysError(Exception):
    """Importing SSH Keys failed."""


class SSHKeyManager(Manager):
    """A utility to manage the colletion of `SSHKey`s."""

    def get_keys_for_user(self, user):
        """Return the text of the ssh keys associated with a user."""
        return SSHKey.objects.filter(user=user).values_list("key", flat=True)

    def from_keysource(
        self, user: User, protocol: str, auth_id: str
    ) -> List[SshKey]:
        """Save SSH Keys for user's protocol and auth_id.

        :param user: The user to save the SSH keys for.
        :param protocol: The protocol 'source'.
        :param auth_id: The protocol username.
        :return: List of imported `SSHKey`s.
        """

        try:
            return service_layer.services.sshkeys.import_keys(
                protocol, auth_id, user.id
            )
        except ValidationException as e:
            # The new service layer uses different exceptions. So the following logic ensure backwards compatibility with
            # the legacy code.
            if len(e.details) > 0:
                detail = e.details[0]
                if detail.field == "key":
                    raise OpenSSHKeyError(detail.message) from None
                elif detail.field == "auth_id":
                    raise ImportSSHKeysError(detail.message) from None


def validate_ssh_public_key(value):
    """Validate that the given value contains a valid SSH public key."""
    try:
        return service_layer.services.sshkeys.normalize_openssh_public_key(
            key=value
        )
    except Exception as error:
        raise ValidationError("Invalid SSH public key: " + str(error))  # noqa: B904


class SSHKey(CleanSave, TimestampedModel):
    """An `SSHKey` represents a user public SSH key.

    Users will be able to access allocated nodes using any of their
    registered keys.

    :ivar user: The user which owns the key.
    :ivar key: The SSH public key.
    :ivar protocol: The source protocol from which the SSH key is pulled.
    :ivar auth_id: The username associated with the protocol.
    """

    objects = SSHKeyManager()

    user = ForeignKey(User, null=False, editable=False, on_delete=CASCADE)

    key = TextField(
        null=False, editable=True, validators=[validate_ssh_public_key]
    )

    protocol = CharField(
        max_length=64,
        null=True,
        editable=True,
        choices=KEYS_PROTOCOL_TYPE_CHOICES,
        blank=True,
    )

    auth_id = CharField(max_length=255, null=True, editable=True, blank=True)

    class Meta:
        verbose_name = "SSH key"

    def __str__(self):
        return self.key

    def clean(self, *args, **kwargs):
        """Make sure there are no duplicate keys.

        Note that this could have been done with Meta.unique_together,
        but it doesn't work for big keys, since the long text strings
        can't be indexed.
        """
        super().clean(*args, **kwargs)
        duplicated_key = SSHKey.objects.filter(
            user=self.user,
            key=self.key,
            protocol=self.protocol,
            auth_id=self.auth_id,
        ).exclude(id=self.id)
        if duplicated_key.exists():
            raise ValidationError(
                "This key has already been added for this user."
            )
