# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Custom field types for the metadata server."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'BinaryField',
    ]

from base64 import (
    b64decode,
    b64encode,
    )

from django.db.models import (
    Field,
    SubfieldBase,
    )
from south.modelsinspector import add_introspection_rules


class Bin(bytes):
    """Wrapper class to convince django that a string is really binary.

    This is really just a "bytes," but gets around an idiosyncracy of Django
    custom field conversions: they must be able to tell on the fly whether a
    value was retrieved from the database (and needs to be converted to a
    python-side value), or whether it's already a python-side object (which
    can stay as it is).  The line between bytes and unicode is dangerously
    thin.

    So, to store a value in a BinaryField, wrap it in a Bin:

        my_model_object.binary_data = Bin(b"\x01\x02\x03")
    """

    def __init__(self, initializer):
        """Wrap a bytes.

        :param initializer: Binary string of data for this Bin.  This must
            be a bytes.  Anything else is almost certainly a mistake, so e.g.
            this constructor will refuse to render None as b'None'.
        :type initializer: bytes
        """
        if not isinstance(initializer, bytes):
            raise AssertionError(
                "Not a binary string: '%s'" % repr(initializer))
        super(Bin, self).__init__(initializer)


# The BinaryField does not introduce any new parameters compared to its
# parent's constructor so South will handle it just fine.
# See http://south.aeracode.org/docs/customfields.html#extending-introspection
# for details.
add_introspection_rules([], ["^metadataserver\.fields\.BinaryField"])


class BinaryField(Field):
    """A field that stores binary data.

    The data is base64-encoded internally, so this is not very efficient.
    Do not use this for large blobs.

    We do not have direct support for binary data in django at the moment.
    It's possible to create a django model Field based by a postgres BYTEA,
    but:

    1. Any data you save gets mis-interpreted as encoded text.  This won't
       be obvious until you test with data that can't be decoded.
    2. Any data you retrieve gets truncated at the first zero byte.
    """

    __metaclass__ = SubfieldBase

    def to_python(self, value):
        """Django overridable: convert database value to python-side value."""
        if isinstance(value, unicode):
            # Encoded binary data from the database.  Convert.
            return Bin(b64decode(value))
        elif value is None or isinstance(value, Bin):
            # Already in python-side form.
            return value
        else:
            raise AssertionError(
                "Invalid BinaryField value (expected unicode): '%s'"
                % repr(value))

    def get_db_prep_value(self, value):
        """Django overridable: convert python-side value to database value."""
        if value is None:
            # Equivalent of a NULL.
            return None
        elif isinstance(value, Bin):
            # Python-side form.  Convert to database form.
            return b64encode(value)
        elif isinstance(value, bytes):
            # Binary string.  Require a Bin to make intent explicit.
            raise AssertionError(
                "Converting a binary string to BinaryField: "
                "either conversion is going the wrong way, or the value "
                "needs to be wrapped in a Bin.")
        elif isinstance(value, unicode):
            # Unicode here is almost certainly a sign of a mistake.
            raise AssertionError(
                "A unicode string is being mistaken for binary data.")
        else:
            raise AssertionError(
                "Invalid BinaryField value (expected Bin): '%s'"
                % repr(value))

    def get_internal_type(self):
        return 'TextField'
