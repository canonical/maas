# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""..."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import re

from django.core.validators import RegexValidator
from django.db.models import Field
import psycopg2.extensions


mac_re = re.compile(r'^([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}$')

validate_mac = RegexValidator(
    regex=mac_re,
    message=u"Enter a valid MAC address (e.g. AA:BB:CC:DD:EE:FF).")


class MACAddressField(Field):
    """Model field type: MAC address."""

    description = "MAC address"

    default_validators = [validate_mac]

    def db_type(self, *args, **kwargs):
        return "macaddr"


class MACAddressAdapter:
    """Adapt a `MACAddressField` for database storage using psycopg2.

    PostgreSQL supports MAC addresses as a native type.
    """

    def __init__(self, value):
        self._wrapped = value

    def getquoted(self):
        """Render this object in SQL."""
        if self._wrapped is None:
            return 'NULL'
        else:
            return "'%s'::macaddr" % self._wrapped


psycopg2.extensions.register_adapter(MACAddressField, MACAddressAdapter)
