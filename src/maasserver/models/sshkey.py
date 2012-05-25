# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

""":class:`SSHKey` and friends."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'SSHKey',
    ]


import binascii
from cgi import escape

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import (
    ForeignKey,
    Manager,
    TextField,
    )
from django.utils.safestring import mark_safe
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from twisted.conch.ssh.keys import (
    BadKeyError,
    Key,
    )


class SSHKeyManager(Manager):
    """A utility to manage the colletion of `SSHKey`s."""

    def get_keys_for_user(self, user):
        """Return the text of the ssh keys associated with a user."""
        return SSHKey.objects.filter(user=user).values_list('key', flat=True)


def validate_ssh_public_key(value):
    """Validate that the given value contains a valid SSH public key."""
    try:
        key = Key.fromString(value)
        if not key.isPublic():
            raise ValidationError(
                "Invalid SSH public key (this key is a private key).")
    except (BadKeyError, binascii.Error):
        raise ValidationError("Invalid SSH public key.")


HELLIPSIS = '&hellip;'


def get_html_display_for_key(key, size):
    """Return a compact HTML representation of this key with a boundary on
    the size of the resulting string.

    A key typically looks like this: 'key_type key_string comment'.
    What we want here is display the key_type and, if possible (i.e. if it
    fits in the boundary that `size` gives us), the comment.  If possible we
    also want to display a truncated key_string.  If the comment is too big
    to fit in, we simply display a cropped version of the whole string.

    :param key: The key for which we want an HTML representation.
    :type name: basestring
    :param size: The maximum size of the representation.  This may not be
        met exactly.
    :type size: int
    :return: The HTML representation of this key.
    :rtype: basestring
    """
    key = key.strip()
    key_parts = key.split(' ', 2)

    if len(key_parts) == 3:
        key_type = key_parts[0]
        key_string = key_parts[1]
        comment = key_parts[2]
        room_for_key = (
            size - (len(key_type) + len(comment) + len(HELLIPSIS) + 2))
        if room_for_key > 0:
            return '%s %.*s%s %s' % (
                escape(key_type, quote=True),
                room_for_key,
                escape(key_string, quote=True),
                HELLIPSIS,
                escape(comment, quote=True))

    if len(key) > size:
        return '%.*s%s' % (
            size - len(HELLIPSIS),
            escape(key, quote=True),
            HELLIPSIS)
    else:
        return escape(key, quote=True)


MAX_KEY_DISPLAY = 50


class SSHKey(CleanSave, TimestampedModel):
    """A `SSHKey` represents a user public SSH key.

    Users will be able to access `Node`s using any of their registered keys.

    :ivar user: The user which owns the key.
    :ivar key: The ssh public key.
    """

    objects = SSHKeyManager()

    user = ForeignKey(User, null=False, editable=False)

    key = TextField(
        null=False, editable=True, validators=[validate_ssh_public_key])

    class Meta(DefaultMeta):
        verbose_name = "SSH key"
        unique_together = ('user', 'key')

    def unique_error_message(self, model_class, unique_check):
        if unique_check == ('user', 'key'):
                return "This key has already been added for this user."
        return super(
            SSHKey, self).unique_error_message(model_class, unique_check)

    def __unicode__(self):
        return self.key

    def display_html(self):
        """Return a compact HTML representation of this key.

        :return: The HTML representation of this key.
        :rtype: basestring
        """
        return mark_safe(get_html_display_for_key(self.key, MAX_KEY_DISPLAY))
