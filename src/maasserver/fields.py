# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Custom model fields."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "MACAddressField",
    "MACAddressFormField",
    ]

from copy import deepcopy
from json import (
    dumps,
    loads,
    )
import re

from django.core.validators import RegexValidator
from django.db.models import (
    Field,
    SubfieldBase,
    )
from django.forms import RegexField
import psycopg2.extensions


mac_re = re.compile(r'^([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}$')


mac_error_msg = "Enter a valid MAC address (e.g. AA:BB:CC:DD:EE:FF)."


validate_mac = RegexValidator(regex=mac_re, message=mac_error_msg)


class MACAddressFormField(RegexField):

    def __init__(self, *args, **kwargs):
        super(MACAddressFormField, self).__init__(
            regex=mac_re, error_message=mac_error_msg, *args, **kwargs)


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


class JSONObjectField(Field):
    """A field that will store any jsonizable python object."""

    __metaclass__ = SubfieldBase

    def to_python(self, value):
        """db -> python: json load."""
        if value is not None:
            if isinstance(value, basestring):
                try:
                    return loads(value)
                except ValueError:
                    pass
            return value
        else:
            return None

    def get_db_prep_value(self, value):
        """python -> db: json dump."""
        if value is not None:
            return dumps(deepcopy(value))
        else:
            return None

    def get_internal_type(self):
        return 'TextField'

    def get_prep_lookup(self, lookup_type, value):
        if lookup_type not in ['exact', 'isnull']:
            raise TypeError("Lookup type %s is not supported." % lookup_type)
        return super(JSONObjectField, self).get_prep_lookup(
            lookup_type, value)
