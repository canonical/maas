# Copyright 2014-2016 Canonical Ltd.
# Copyright 2014 Cloudbase Solutions SRL.
# This software is licensed under the GNU Affero General Public License
# version 3 (see the file LICENSE).

""":class:`SSLKey` and friends."""

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import CASCADE, ForeignKey, Manager, TextField
from django.utils.safestring import mark_safe
from OpenSSL import crypto

from maascommon.sslkey import get_html_display_for_key
from maasserver import logger
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


class SSLKeyManager(Manager):
    """A utility to manage the colletion of `SSLKey`s."""

    def get_keys_for_user(self, user):
        """Return the text of the ssl keys associated with a user."""
        return SSLKey.objects.filter(user=user).values_list("key", flat=True)


def validate_ssl_key(value):
    """Validate that the given value contains a valid SSL key."""
    try:
        crypto.load_certificate(crypto.FILETYPE_PEM, value)
    except Exception:
        # crypto.load_certificate raises all sorts of exceptions.
        # Here, we catch them all and return a ValidationError since this
        # method only aims at validating keys and not return the exact cause of
        # the failure.
        logger.exception("Invalid SSL key.")
        raise ValidationError("Invalid SSL key.")  # noqa: B904


class SSLKey(CleanSave, TimestampedModel):
    """An `SSLKey` represents a user SSL key.

    Users will be able to access Windows winrm service with
    any of the registered keys.

    :ivar user: The user which owns the key.
    :ivar key: The SSL key.
    """

    objects = SSLKeyManager()

    user = ForeignKey(User, null=False, editable=False, on_delete=CASCADE)

    key = TextField(
        null=False, blank=False, editable=True, validators=[validate_ssl_key]
    )

    class Meta:
        verbose_name = "SSL key"
        unique_together = ("user", "key")

    def unique_error_message(self, model_class, unique_check):
        if unique_check == ("user", "key"):
            return "This key has already been added for this user."
        return super().unique_error_message(model_class, unique_check)

    def __str__(self):
        return self.key

    def display_html(self):
        """Return a compact HTML representation of this key.

        :return: The HTML representation of this key.
        :rtype: unicode
        """
        return mark_safe(get_html_display_for_key(self.key))
