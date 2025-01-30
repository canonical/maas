# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

""":class:`SSHKey` and friends."""


from html import escape
from typing import List

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import CASCADE, CharField, ForeignKey, Manager, TextField
from django.utils.safestring import mark_safe

from maasserver.enum import KEYS_PROTOCOL_TYPE_CHOICES
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.sqlalchemy import exec_async, servicelayer
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

        with servicelayer() as services:
            try:
                return exec_async(
                    services.sshkeys.import_keys(protocol, auth_id, user.id)
                )
            except ValidationException as e:
                # The new service layer uses different exceptions. So the following logic ensure backwards compatibility with
                # the legacy code.
                if len(e.details) > 0:
                    detail = e.details[0]
                    if detail.field == "key":
                        raise OpenSSHKeyError(detail.message)
                    elif detail.field == "auth_id":
                        raise ImportSSHKeysError(detail.message)


def validate_ssh_public_key(value):
    """Validate that the given value contains a valid SSH public key."""
    try:
        with servicelayer() as services:
            return exec_async(
                services.sshkeys.normalize_openssh_public_key(key=value)
            )
    except Exception as error:
        raise ValidationError("Invalid SSH public key: " + str(error))


HELLIPSIS = "&hellip;"


def get_html_display_for_key(key, size):
    """Return a compact HTML representation of this key with a boundary on
    the size of the resulting string.

    A key typically looks like this: 'key_type key_string comment'.
    What we want here is display the key_type and, if possible (i.e. if it
    fits in the boundary that ``size`` gives us), the comment.  If possible we
    also want to display a truncated key_string.  If the comment is too big
    to fit in, we simply display a cropped version of the whole string.

    :param key: The key for which we want an HTML representation.
    :type name: unicode
    :param size: The maximum size of the representation.  This may not be
        met exactly.
    :type size: int
    :return: The HTML representation of this key.
    :rtype: unicode
    """
    key = key.strip()
    key_parts = key.split(" ", 2)

    if len(key_parts) == 3:
        key_type = key_parts[0]
        key_string = key_parts[1]
        comment = key_parts[2]
        room_for_key = size - (
            len(key_type) + len(comment) + len(HELLIPSIS) + 2
        )
        if room_for_key > 0:
            return "%s %.*s%s %s" % (
                escape(key_type, quote=True),
                room_for_key,
                escape(key_string, quote=True),
                HELLIPSIS,
                escape(comment, quote=True),
            )

    if len(key) > size:
        return "%.*s%s" % (
            size - len(HELLIPSIS),
            escape(key, quote=True),
            HELLIPSIS,
        )
    else:
        return escape(key, quote=True)


DEFAULT_KEY_DISPLAY = 50


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

    def display_html(self, key_size=None):
        """Return a compact HTML representation of this key.

        :return: The HTML representation of this key.
        :rtype: unicode
        """
        if key_size is None:
            key_size = DEFAULT_KEY_DISPLAY
        return mark_safe(get_html_display_for_key(self.key, key_size))

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
