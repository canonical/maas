# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Custom field types for the metadata server."""

from base64 import b64decode, b64encode

from django.db import connection
from django.db.models import Field


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

    def __new__(cls, initializer):
        """Wrap a bytes.

        :param initializer: Binary string of data for this Bin.  This must
            be a bytes.  Anything else is almost certainly a mistake, so e.g.
            this constructor will refuse to render None as b'None'.
        :type initializer: bytes
        """
        # We can't do this in __init__, because it passes its argument into
        # the upcall.  It ends up in object.__init__, which sometimes issues
        # a DeprecationWarning because it doesn't want any arguments.
        # Those warnings would sometimes make their way into logs, breaking
        # tests that checked those logs.
        if not isinstance(initializer, bytes):
            raise AssertionError(
                "Not a binary string: '%s'" % repr(initializer)
            )
        return super().__new__(cls, initializer)

    def __emittable__(self):
        """Emit base-64 encoded bytes.

        Exists as a hook for Piston's JSON encoder.
        """
        return b64encode(self).decode("ascii")


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

    def to_python(self, value):
        """Django overridable: convert database value to python-side value."""
        if isinstance(value, str):
            # Encoded binary data from the database.  Convert.
            return Bin(b64decode(value))
        elif value is None or isinstance(value, Bin):
            # Already in python-side form.
            return value
        else:
            raise AssertionError(
                "Invalid BinaryField value (expected unicode): '%s'"
                % repr(value)
            )

    def from_db_value(self, value, expression, connection):
        return self.to_python(value)

    def get_db_prep_value(self, value, connection=None, prepared=False):
        """Django overridable: convert python-side value to database value."""
        if value is None:
            # Equivalent of a NULL.
            return None
        elif isinstance(value, Bin):
            # Python-side form.  Convert to database form.
            return b64encode(value).decode("ascii")
        elif isinstance(value, bytes):
            # Binary string.  Require a Bin to make intent explicit.
            raise AssertionError(
                "Converting a binary string to BinaryField: "
                "either conversion is going the wrong way, or the value "
                "needs to be wrapped in a Bin."
            )
        elif isinstance(value, str):
            # Django 1.7 migration framework generates the default value based
            # on the 'internal_type' which, in this instance, is 'TextField';
            # Here we cope with the default empty value instead of raising
            # an exception.
            if value == "":
                return ""
            # Unicode here is almost certainly a sign of a mistake.
            raise AssertionError(
                "A unicode string is being mistaken for binary data."
            )
        else:
            raise AssertionError(
                "Invalid BinaryField value (expected Bin): '%s'" % repr(value)
            )

    def get_internal_type(self):
        return "TextField"

    def _get_default(self):
        """Cargo-cult of Django's `Field.get_default`.

        Django is totally smoking crack on this one. It forces a
        unicode string out of the default which is demonstrably not
        unicode. This corrects that behaviour.

        """
        if self.has_default():
            if callable(self.default):
                return self.default()
            return self.default
        if not self.empty_strings_allowed:
            return None
        if self.null:
            if not connection.features.interprets_empty_strings_as_nulls:
                return None
        return b""

    def get_default(self):
        """Override Django's crack-smoking ``Field.get_default``."""
        default = self._get_default()
        return None if default is None else Bin(default)
