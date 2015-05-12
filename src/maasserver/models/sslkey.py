# Copyright 2014-2015 Cloudbase Solutions SRL.
# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

""":class:`SSLKey` and friends."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'SSLKey',
    ]


from cgi import escape

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import (
    ForeignKey,
    Manager,
    TextField,
)
from django.utils.safestring import mark_safe
from maasserver import (
    DefaultMeta,
    logger,
)
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from OpenSSL import crypto


class SSLKeyManager(Manager):
    """A utility to manage the colletion of `SSLKey`s."""

    def get_keys_for_user(self, user):
        """Return the text of the ssl keys associated with a user."""
        return SSLKey.objects.filter(user=user).values_list('key', flat=True)


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
        raise ValidationError("Invalid SSL key.")


def find_ssl_common_name(subject):
    """Returns the common name for the ssl key."""
    for component in subject.get_components():
        if len(component) < 2:
            continue
        if component[0] == 'CN':
            return component[1]
    return None


def get_html_display_for_key(key):
    """Returns the html escaped string for the key."""
    cert = crypto.load_certificate(crypto.FILETYPE_PEM, key)
    subject = cert.get_subject()
    md5 = cert.digest('MD5')
    cn = find_ssl_common_name(subject)
    if cn is not None:
        key = "%s %s" % (cn, md5)
    else:
        key = md5
    return escape(key, quote=True)


class SSLKey(CleanSave, TimestampedModel):
    """An `SSLKey` represents a user SSL key.

    Users will be able to access Windows winrm service with
    any of the registered keys.

    :ivar user: The user which owns the key.
    :ivar key: The SSL key.

    """
    objects = SSLKeyManager()

    user = ForeignKey(User, null=False, editable=False)
    key = TextField(
        null=False, blank=False, editable=True, validators=[validate_ssl_key])

    class Meta(DefaultMeta):
        verbose_name = "SSL key"
        unique_together = ('user', 'key')

    def unique_error_message(self, model_class, unique_check):
        if unique_check == ('user', 'key'):
            return "This key has already been added for this user."
        return super(
            SSLKey, self).unique_error_message(model_class, unique_check)

    def __unicode__(self):
        return self.key

    def display_html(self):
        """Return a compact HTML representation of this key.

        :return: The HTML representation of this key.
        :rtype: unicode
        """
        return mark_safe(get_html_display_for_key(self.key))
