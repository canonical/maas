# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Custom model fields."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "MAC",
    "MACAddressField",
    "MACAddressFormField",
    "register_mac_type",
    ]

from copy import deepcopy
from json import (
    dumps,
    loads,
    )
import re

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db.models import (
    Field,
    SubfieldBase,
    )
from django.forms import (
    ModelChoiceField,
    RegexField,
    )
import psycopg2.extensions
from south.modelsinspector import add_introspection_rules


mac_re = re.compile(r'^\s*([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}\s*$')


mac_error_msg = "Enter a valid MAC address (e.g. AA:BB:CC:DD:EE:FF)."

mac_validator = RegexValidator(regex=mac_re, message=mac_error_msg)


def validate_mac(value):
    """Django validator for a MAC."""
    if isinstance(value, MAC):
        value = value.get_raw()
    mac_validator(value)


# The MACAddressField, JSONObjectField and XMLField don't introduce any new
# parameters compared to their parent's constructors so South will handle
# them just fine.
# See http://south.aeracode.org/docs/customfields.html#extending-introspection
# for details.
add_introspection_rules(
    [], [
        "^maasserver\.fields\.MACAddressField",
        "^maasserver\.fields\.JSONObjectField",
        "^maasserver\.fields\.XMLField",
    ])


class NodeGroupFormField(ModelChoiceField):
    """Form field: reference to a :class:`NodeGroup`.

    Node groups are identified by their subnets.  More precisely: this
    field will accept any IP as an identifier for the nodegroup whose subnet
    contains the IP address.

    Unless `queryset` is explicitly given, this field covers all NodeGroup
    objects.
    """

    def __init__(self, **kwargs):
        # Avoid circular imports.
        from maasserver.models import NodeGroup

        kwargs.setdefault('queryset', NodeGroup.objects.all())
        super(NodeGroupFormField, self).__init__(**kwargs)

    def label_from_instance(self, nodegroup):
        """Django method: get human-readable choice label for nodegroup."""
        interface = nodegroup.get_managed_interface()
        if interface is None:
            return nodegroup.name
        else:
            return "%s: %s" % (nodegroup.name, interface.ip)

    def clean(self, value):
        """Django method: provide expected output for various inputs.

        There seems to be no clear specification on what `value` can be.
        This method accepts the types that we see in practice: raw bytes
        containing an IP address, a :class:`NodeGroup`, or the nodegroup's
        numerical id in text form.

        If no nodegroup is indicated, defaults to the master.
        """
        # Avoid circular imports.
        from maasserver.models import NodeGroup

        if value in (None, '', b''):
            nodegroup_id = NodeGroup.objects.ensure_master().id
        elif isinstance(value, NodeGroup):
            nodegroup_id = value.id
        elif isinstance(value, unicode) and value.isnumeric():
            nodegroup_id = int(value)
        elif isinstance(value, bytes) and '.' not in value:
            nodegroup_id = int(value)
        else:
            raise ValidationError("Invalid nodegroup: %s." % value)
        return super(NodeGroupFormField, self).clean(nodegroup_id)


class MACAddressFormField(RegexField):
    """Form field type: MAC address."""

    def __init__(self, *args, **kwargs):
        super(MACAddressFormField, self).__init__(
            regex=mac_re, error_message=mac_error_msg, *args, **kwargs)


class MACAddressField(Field):
    """Model field type: MAC address."""

    __metaclass__ = SubfieldBase

    description = "MAC address"

    default_validators = [validate_mac]

    def db_type(self, *args, **kwargs):
        return "macaddr"


class MAC:
    """A MAC address represented as a database value.

    PostgreSQL supports MAC addresses as a native type.  They show up
    client-side as this class.  It is essentially a wrapper for either a
    string, or None.
    """

    def __init__(self, value):
        """Wrap a MAC address, or None, into a `MAC`.

        :param value: A MAC address, in the form of a string or a `MAC`;
            or None.
        """
        if isinstance(value, MAC):
            # Avoid double-wrapping.  It's the value that matters, not the
            # MAC object that wraps it.
            value = value.get_raw()
        elif isinstance(value, bytes):
            value = value.decode("ascii")
        else:
            # TODO bug=1215447: Remove this assertion.
            assert value is None or isinstance(value, unicode)
        # The wrapped attribute is stored as self._wrapped, following
        # ISQLQuote's example.
        self._wrapped = value

    def __conform__(self, protocol):
        """Tell psycopg2 that this type implements the adapter protocol."""
        # The psychopg2 docs say to check that the protocol is ISQLQuote,
        # but not what to do if it isn't.
        assert protocol == psycopg2.extensions.ISQLQuote, (
            "Unsupported psycopg2 adapter protocol: %s" % protocol)
        return self

    def getquoted(self):
        """Render this object in SQL.

        This is part of psycopg2's adapter protocol.
        """
        value = self.get_raw()
        if value is None:
            return 'NULL'
        else:
            return "'%s'::macaddr" % value

    def get_raw(self):
        """Return the wrapped value."""
        return self._wrapped

    @staticmethod
    def parse(value, cur):
        """Turn a value as received from the database into a MAC."""
        return MAC(value)

    def __repr__(self):
        """Represent the MAC as a string.
        """
        return self.get_raw()

    def __eq__(self, other):
        # Two MACs are equal if they wrap the same value.
        #
        # Also, a MAC is equal to the value it wraps.  This is non-commutative,
        # but it supports Django code that compares input values to various
        # kinds of "null" or "empty."
        if isinstance(other, MAC):
            other = other.get_raw()
        return self.get_raw() == other

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return self.get_raw().__hash__()


def register_mac_type(cursor):
    """Register our `MAC` type with psycopg2 and Django."""

    # This is standard, but not built-in, magic to register a type in
    # psycopg2: execute a query that returns a field of the corresponding
    # database type, then get its oid out of the cursor, use that to create
    # a "typecaster" in psycopg (by calling new_type(), confusingly!), then
    # register that type in psycopg.
    cursor.execute("SELECT NULL::macaddr")
    oid = cursor.description[0][1]
    mac_caster = psycopg2.extensions.new_type((oid, ), b"macaddr", MAC.parse)
    psycopg2.extensions.register_type(mac_caster)

    # Now do the same for the type array-of-MACs.  The "typecaster" created
    # for MAC is passed in; it gets used for parsing an individual element
    # of an array's text representatoin as received from the database.
    cursor.execute("SELECT '{}'::macaddr[]")
    oid = cursor.description[0][1]
    psycopg2.extensions.register_type(psycopg2.extensions.new_array_type(
        (oid, ), b"macaddr", mac_caster))


class JSONObjectField(Field):
    """A field that will store any jsonizable python object."""

    __metaclass__ = SubfieldBase

    def to_python(self, value):
        """db -> python: json load."""
        assert not isinstance(value, bytes)
        if value is not None:
            if isinstance(value, unicode):
                try:
                    return loads(value)
                except ValueError:
                    pass
            return value
        else:
            return None

    def get_db_prep_value(self, value, connection=None, prepared=False):
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


class XMLField(Field):
    """A field for storing xml natively.

    This is not like the removed Django XMLField which just added basic python
    level checking on top of a text column.

    Really inserts should be wrapped like `XMLPARSE(DOCUMENT value)` but it's
    hard to do from django so rely on postgres supporting casting from char.
    """

    description = "XML document or fragment"

    def db_type(self, connection):
        return "xml"

    def get_db_prep_lookup(self, lookup_type, value, **kwargs):
        """Limit lookup types to those that work on xml.

        Unlike character fields the xml type is non-comparible, see:
        <http://www.postgresql.org/docs/devel/static/datatype-xml.html>
        """
        if lookup_type != 'isnull':
            raise TypeError("Lookup type %s is not supported." % lookup_type)
        return super(XMLField, self).get_db_prep_lookup(
            lookup_type, value, **kwargs)
