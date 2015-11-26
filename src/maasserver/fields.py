# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Custom model and form fields."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "CIDRField",
    "EditableBinaryField",
    "IPListFormField",
    "IPv4CIDRField",
    "MAASIPAddressField",
    "MAC",
    "MACAddressField",
    "MACAddressFormField",
    "register_mac_type",
    "VerboseRegexValidator",
    ]

from copy import deepcopy
from json import (
    dumps,
    loads,
)
import re

import django
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import connections
from django.db.models import (
    BinaryField,
    CharField,
    Field,
    GenericIPAddressField,
    IntegerField,
    SubfieldBase,
)
from django.db.models.fields.subclassing import Creator
from django.utils.encoding import force_text
from maasserver.utils.django import has_builtin_migrations
from maasserver.utils.dns import validate_domain_name
from maasserver.utils.orm import (
    get_one,
    validate_in_transaction,
)
from netaddr import (
    AddrFormatError,
    IPNetwork,
)
import psycopg2.extensions


MAC_RE = re.compile(r'^\s*([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}\s*$')

MAC_ERROR_MSG = "'%(value)s' is not a valid MAC address."


class VerboseRegexValidator(RegexValidator):
    """A verbose `RegexValidator`.

    This `RegexValidator` includes the checked value in the rendered error
    message when the validation fails.
    """
    # Set a bugus code to circumvent Django's attempt to re-interpret a
    # validator's error message using the field's message it is attached
    # to.
    code = 'bogus-code'

    def __call__(self, value):
        """Validates that the input matches the regular expression."""
        if not self.regex.search(force_text(value)):
            raise ValidationError(
                self.message % {'value': value}, code=self.code)


mac_validator = VerboseRegexValidator(regex=MAC_RE, message=MAC_ERROR_MSG)


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
if not has_builtin_migrations():
    from south.modelsinspector import add_introspection_rules
    add_introspection_rules(
        [], [
            "^maasserver\.fields\.MACAddressField",
            "^maasserver\.fields\.JSONObjectField",
            "^maasserver\.fields\.XMLField",
            "^maasserver\.fields\.EditableBinaryField",
            "^maasserver\.fields\.MAASIPAddressField",
            "^maasserver\.fields\.LargeObjectField",
            "^maasserver\.fields\.CIDRField",
            "^maasserver\.fields\.IPv4CIDRField",
            "^maasserver\.fields\.DomainNameField",
        ])


class NodeGroupFormField(forms.ModelChoiceField):
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
        interfaces = sorted(
            interface.ip for interface in nodegroup.get_managed_interfaces())
        if len(interfaces) > 0:
            return "%s: %s" % (nodegroup.name, ', '.join(interfaces))
        else:
            return nodegroup.name

    def _get_nodegroup_from_string(self, value=None):
        """Identify a `NodeGroup` ID from a text value.

        :param value: A `unicode` that identifies a `NodeGroup` somehow: as a
            numerical ID in text form, as a UUID, as a cluster name, or as the
            empty string to denote the master nodegroup.  `None` also gets the
            master nodegroup.
        :return: Matching `NodeGroup`, or `None`.
        """
        # Avoid circular imports.
        from maasserver.models import NodeGroup

        if value is None or value == '':
            # No identification given.  Default to the master.
            return NodeGroup.objects.ensure_master()

        if value.isnumeric():
            # Try value as an ID.
            nodegroup = get_one(NodeGroup.objects.filter(id=int(value)))
            if nodegroup is not None:
                return nodegroup

        # Try value as a UUID.
        nodegroup = get_one(NodeGroup.objects.filter(uuid=value))
        if nodegroup is not None:
            return nodegroup

        # Try value as a cluster name.
        return get_one(NodeGroup.objects.filter(cluster_name=value))

    def clean(self, value):
        """Django method: provide expected output for various inputs.

        There seems to be no clear specification on what `value` can be.
        This method accepts the types that we see in practice:
         * :class:`NodeGroup`
         * the nodegroup's numerical id in text form
         * the nodegroup's uuid
         * the nodegroup's cluster_name

        If no nodegroup is indicated, it defaults to the master.
        """
        # Avoid circular imports.
        from maasserver.models import NodeGroup

        if isinstance(value, bytes):
            value = value.decode('utf-8')

        if value is None or isinstance(value, unicode):
            nodegroup = self._get_nodegroup_from_string(value)
        elif isinstance(value, NodeGroup):
            nodegroup = value
        else:
            nodegroup = None

        if nodegroup is None:
            raise ValidationError("Invalid nodegroup: %s." % value)

        return nodegroup


class StrippedCharField(forms.CharField):
    """A CharField that will strip surrounding whitespace before validation."""

    def clean(self, value):
        value = self.to_python(value).strip()
        return super(StrippedCharField, self).clean(value)


class VerboseRegexField(forms.CharField):

    def __init__(self, regex, message, *args, **kwargs):
        """A field that validates its value with a regular expression.

        :param regex: Either a string or a compiled regular expression object.
        :param message: Error message to use when the validation fails.
        """
        super(VerboseRegexField, self).__init__(*args, **kwargs)
        self.validators.append(
            VerboseRegexValidator(regex=regex, message=message))


class MACAddressFormField(VerboseRegexField):
    """Form field type: MAC address."""

    def __init__(self, *args, **kwargs):
        super(MACAddressFormField, self).__init__(
            regex=MAC_RE, message=MAC_ERROR_MSG, *args, **kwargs)


class MACAddressField(Field):
    """Model field type: MAC address."""

    __metaclass__ = SubfieldBase

    description = "MAC address"

    default_validators = [validate_mac]

    def db_type(self, *args, **kwargs):
        return "macaddr"

    def to_python(self, value):
        return MAC(value)


class MAC:
    """A MAC address represented as a database value.

    PostgreSQL supports MAC addresses as a native type. They show up
    client-side as this class. It is essentially a wrapper for a string.

    This NEVER represents a null or empty MAC address.
    """

    def __new__(cls, value):
        """Return `None` if `value` is `None` or the empty string."""
        if value is None:
            return None
        elif isinstance(value, (bytes, unicode)):
            return None if len(value) == 0 else super(MAC, cls).__new__(cls)
        else:
            return super(MAC, cls).__new__(cls)

    def __init__(self, value):
        """Wrap a MAC address, or None, into a `MAC`.

        :param value: A MAC address, in the form of a string or a `MAC`;
            or None.
        """
        # The wrapped attribute is stored as self._wrapped, following
        # ISQLQuote's example.
        if isinstance(value, MAC):
            self._wrapped = value._wrapped
        elif isinstance(value, bytes):
            self._wrapped = value.decode("ascii")
        elif isinstance(value, unicode):
            self._wrapped = value
        else:
            raise TypeError("expected MAC or string, got: %r" % (value,))

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
        return "'%s'::macaddr" % self._wrapped

    def get_raw(self):
        """Return the wrapped value."""
        return self._wrapped

    @property
    def raw(self):
        """The MAC address as a string."""
        return self._wrapped

    @classmethod
    def parse(cls, value, cur):
        """Turn a value as received from the database into a MAC."""
        return cls(value)

    def __repr__(self):
        """Represent the MAC as a string."""
        return "<MAC %s>" % self._wrapped

    def __unicode__(self):
        """Represent the MAC as a Unicode string."""
        return self._wrapped

    def __str__(self):
        """Represent the MAC as a byte string."""
        return self._wrapped.encode("ascii")

    def __eq__(self, other):
        """Two `MAC`s are equal if they wrap the same value.

        A MAC is is also equal to the value it wraps. This is non-commutative,
        but it supports Django code that compares input values to various
        kinds of "null" or "empty."
        """
        if isinstance(other, MAC):
            return self._wrapped == other._wrapped
        else:
            return self._wrapped == other

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash(self._wrapped)


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
    # of an array's text representation as received from the database.
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


class EditableBinaryField(BinaryField):
    """An editable binary field.

    An editable version of Django's BinaryField.
    """

    def __init__(self, *args, **kwargs):
        super(EditableBinaryField, self).__init__(*args, **kwargs)
        self.editable = True

    def deconstruct(self):
        # Override deconstruct not to fail on the removal of the 'editable'
        # field: the Django migration module assumes the field has its default
        # value (False).
        return Field.deconstruct(self)


class MAASIPAddressField(GenericIPAddressField):
    """A version of GenericIPAddressField with a custom get_internal_type().

    This class exists to work around a bug in Django that inserts a HOST() cast
    on the IP, causing the wrong comparison on the IP field.  See
    https://code.djangoproject.com/ticket/11442 for details.
    """

    def get_internal_type(self):
        """Returns a value different from 'GenericIPAddressField' and
        'IPAddressField' to force Django not to use a HOST() case when
        performing operation on this field.
        """
        return "IPField"

    def db_type(self, connection):
        """Returns the database column data type for IPAddressField.

        Override the default implementation which uses get_internal_type()
        and force a 'inet' type field.
        """
        return 'inet'


class LargeObjectFile:
    """Large object file.

    Proxy the access from this object to psycopg2.
    """
    def __init__(self, oid=0, field=None, instance=None, block_size=(1 << 16)):
        self.oid = oid
        self.field = field
        self.instance = instance
        self.block_size = block_size
        self._lobject = None

    def __getattr__(self, name):
        if self._lobject is None:
            raise IOError("LargeObjectFile is not opened.")
        return getattr(self._lobject, name)

    def __enter__(self, *args, **kwargs):
        return self

    def __exit__(self, *args, **kwargs):
        self.close()

    def __iter__(self):
        return self

    def open(self, mode="rwb", new_file=None, using="default",
             connection=None):
        """Opens the internal large object instance."""
        if connection is None:
            connection = connections[using]
        validate_in_transaction(connection)
        self._lobject = connection.connection.lobject(
            self.oid, mode, 0, new_file)
        self.oid = self._lobject.oid
        return self

    def unlink(self):
        """Removes the large object."""
        if self._lobject is None:
            # Need to open the lobject so we get a reference to it in the
            # database, to perform the unlink.
            self.open()
            self.close()
        self._lobject.unlink()
        self._lobject = None
        self.oid = 0

    def next(self):
        r = self.read(self.block_size)
        if len(r) == 0:
            raise StopIteration
        return r


class LargeObjectDescriptor(Creator):
    """LargeObjectField descriptor."""

    def __set__(self, instance, value):
        value = self.field.to_python(value)
        if value is not None:
            if not isinstance(value, LargeObjectFile):
                value = LargeObjectFile(value, self.field, instance)
        instance.__dict__[self.field.name] = value


class LargeObjectField(IntegerField):
    """A field that stores large amounts of data into postgres large object
    storage.

    Internally the field on the model is an `oid` field, that returns a proxy
    to the referenced large object.
    """

    def __init__(self, *args, **kwargs):
        self.block_size = kwargs.pop('block_size', 1 << 16)
        super(LargeObjectField, self).__init__(*args, **kwargs)

    # In django 1.8 this is a property and is needed. To support upgrades
    # from MAAS <2.0 we need to support running under django 1.6.
    if django.VERSION >= (1, 7):
        @property
        def validators(self):
            # No validation. IntegerField will add incorrect validation. This
            # removes that validation.
            return []

    def db_type(self, connection):
        """Returns the database column data type for LargeObjectField."""
        # oid is the column type postgres uses to reference a large object
        return 'oid'

    def contribute_to_class(self, cls, name):
        """Set the descriptor for the large object."""
        super(LargeObjectField, self).contribute_to_class(cls, name)
        setattr(cls, self.name, LargeObjectDescriptor(self))

    def get_db_prep_value(self, value, connection=None, prepared=False):
        """python -> db: `oid` value"""
        if value is None:
            return None
        if isinstance(value, LargeObjectFile):
            if value.oid > 0:
                return value.oid
            raise AssertionError(
                "LargeObjectFile's oid must be greater than 0.")
        raise AssertionError(
            "Invalid LargeObjectField value (expected LargeObjectFile): '%s'"
            % repr(value))

    def to_python(self, value):
        """db -> python: `LargeObjectFile`"""
        if value is None:
            return None
        elif isinstance(value, LargeObjectFile):
            return value
        elif isinstance(value, (int, long)):
            return LargeObjectFile(value, self, self.model, self.block_size)
        raise AssertionError(
            "Invalid LargeObjectField value (expected integer): '%s'"
            % repr(value))


def parse_cidr(value):
    try:
        return unicode(IPNetwork(value).cidr)
    except AddrFormatError as e:
        raise ValidationError(e.message)


class CIDRField(Field):
    description = "PostgreSQL CIDR field"

    __metaclass__ = SubfieldBase

    def db_type(self, connection):
        return 'cidr'

    def get_prep_value(self, value):
        if value is None or value == '':
            return None
        return parse_cidr(value)

    def from_db_value(self, value, expression, connection, context):
        if value is None:
            return value
        return parse_cidr(value)

    def to_python(self, value):
        if value is None or value == '':
            return None
        if isinstance(value, IPNetwork):
            return unicode(value)
        if not value:
            return value
        return parse_cidr(value)

    def formfield(self, **kwargs):
        defaults = {
            'form_class': forms.CharField,
        }
        defaults.update(kwargs)
        return super(CIDRField, self).formfield(**defaults)


class IPv4CIDRField(CIDRField):
    """IPv4-only CIDR"""

    def to_python(self, value):
        if value is None or value == '':
            return None
        else:
            try:
                cidr = IPNetwork(value)
            except AddrFormatError:
                raise ValidationError("Invalid network: %s" % value)
            if cidr.cidr.version != 4:
                raise ValidationError(
                    "%s: Only IPv4 networks supported." % value)
        return unicode(cidr.cidr)


class IPListFormField(forms.CharField):
    """Accepts a space/comma separated list of IP addresses.

    This field normalizes the list to a space-separated list.
    """
    separators = re.compile('[,\s]+')

    def clean(self, value):
        if value is None:
            return None
        else:
            ips = re.split(self.separators, value)
            ips = [ip.strip() for ip in ips if ip != '']
            for ip in ips:
                try:
                    GenericIPAddressField().clean(ip, model_instance=None)
                except ValidationError:
                    raise ValidationError(
                        "Invalid IP address: %s; provide a list of "
                        "space-separated IP addresses" % ip)
            return ' '.join(ips)


class CaseInsensitiveChoiceField(forms.ChoiceField):
    """ChoiceField that allows the input to be case insensitive."""

    def to_python(self, value):
        if value not in self.empty_values:
            value = value.lower()
        return super(CaseInsensitiveChoiceField, self).to_python(value)


class SpecifierOrModelChoiceField(forms.ModelChoiceField):
    """ModelChoiceField which is also able to accept input in the format
    of a specifiers string.
    """

    def to_python(self, value):
        try:
            return super(SpecifierOrModelChoiceField, self).to_python(value)
        except ValidationError as e:
            if isinstance(value, unicode):
                object_id = self.queryset.get_object_id(value)
                if object_id is None:
                    obj = get_one(self.queryset.filter_by_specifiers(
                        value), exception_class=ValidationError)
                    if obj is not None:
                        return obj
                else:
                    return self.queryset.get(id=object_id)
            raise e


class DomainNameField(CharField):
    """Custom Django field that strips whitespace and trailing '.' characters
    from DNS domain names before validating and saving to the database. Also,
    validates that the domain name is valid according to RFCs 952 and 1123.
    (Note that this field type should NOT be used for hostnames, since the set
    of valid hostnames is smaller than the set of valid domain names.)
    """
    def __init__(self, *args, **kwargs):
        validators = kwargs.pop('validators', [])
        validators.append(validate_domain_name)
        kwargs['validators'] = validators
        super(DomainNameField, self).__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super(DomainNameField, self).deconstruct()
        del kwargs['validators']
        return name, path, args, kwargs

    # Here we are using (abusing?) the to_pytion() function to coerce and
    # normalize this type. Django does not have a function intended purely
    # to normalize before saving to the database, so to_python() is the next
    # closest alternative. For more information, see:
    # https://docs.djangoproject.com/en/1.6/ref/forms/validation/
    # https://code.djangoproject.com/ticket/6362
    def to_python(self, value):
        value = super(DomainNameField, self).to_python(value)
        value = value.strip().rstrip('.')
        return value
