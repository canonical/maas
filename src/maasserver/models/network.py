# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for networks."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'Network',
    'parse_network_spec',
    ]


from abc import (
    ABCMeta,
    abstractmethod,
    )

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db.models import (
    CharField,
    Manager,
    Model,
    PositiveSmallIntegerField,
    TextField,
    )
from maasserver import DefaultMeta
from maasserver.fields import MAASIPAddressField
from maasserver.models.cleansave import CleanSave
from netaddr import IPAddress
from netaddr.core import AddrFormatError
from provisioningserver.utils.network import make_network

# Network name validator.  Must consist of alphanumerical characters and/or
# dashes.
NETWORK_NAME_VALIDATOR = RegexValidator('^[\w-]+$')


def strip_type_tag(type_tag, specifier):
    """Return a network specifier minus its type tag."""
    prefix = type_tag + ':'
    assert specifier.startswith(prefix)
    return specifier[len(prefix):]


class NetworkSpecifier:
    """A :class:`NetworkSpecifier` identifies a :class:`Network`.

    For example, in placement constraints, a user may specify that a node
    must be attached to a certain network.  They identify the network through
    a network specifier, which may be its name (`dmz`), an IP address
    (`ip:10.12.0.0`), or a VLAN tag (`vlan:15` or `vlan:0xf`).

    Each type of network specifier has its own `NetworkSpecifier`
    implementation class.  The class constructor validates and parses a
    network specifier of its type, and the object knows how to retrieve
    whatever network it identifies from the database.
    """
    __metaclass__ = ABCMeta

    # Most network specifiers start with a type tag followed by a colon, e.g.
    # "ip:10.1.0.0".
    type_tag = None

    @abstractmethod
    def find_network(self):
        """Load the identified :class:`Network` from the database.

        :raise Network.DoesNotExist: If no network matched the specifier.
        :return: The :class:`Network`.
        """


class NameSpecifier(NetworkSpecifier):
    """Identify a network by its name.

    This type of network specifier has no type tag; it's just the name.  A
    network name cannot contain colon (:) characters.
    """

    def __init__(self, spec):
        NETWORK_NAME_VALIDATOR(spec)
        self.name = spec

    def find_network(self):
        return Network.objects.get(name=self.name)


class IPSpecifier(NetworkSpecifier):
    """Identify a network by any IP address it contains.

    The IP address is prefixed with a type tag `ip:`, e.g. `ip:10.1.1.0`.
    It can name any IP address within the network, including its base address,
    its broadcast address, or any host address that falls in its IP range.
    """
    type_tag = 'ip'

    def __init__(self, spec):
        ip_string = strip_type_tag(self.type_tag, spec)
        try:
            self.ip = IPAddress(ip_string)
        except AddrFormatError as e:
            raise ValidationError("Invalid IP address: %s." % e)

    def find_network(self):
        # Use all().  We could narrow down the database query, but not by a
        # lot -- and this will cache better.  The number of networks should
        # not be so large that querying them from the database becomes a
        # problem for the region controller.
        for network in Network.objects.all():
            if self.ip in network.get_network():
                # Networks don't overlap, so there can be only one.
                return network
        raise Network.DoesNotExist()


class VLANSpecifier(NetworkSpecifier):
    """Identify a network by its (nonzero) VLAN tag.

    This only applies to VLANs.  The VLAN tag is a numeric value prefixed with
    a type tag of `vlan:`, e.g. `vlan:12`.  Tags may also be given in
    hexadecimal form: `vlan:0x1a`.  This is case-insensitive.
    """
    type_tag = 'vlan'

    def __init__(self, spec):
        vlan_string = strip_type_tag(self.type_tag, spec)
        if vlan_string.lower().startswith('0x'):
            # Hexadecimal.
            base = 16
        else:
            # Decimal.
            base = 10
        try:
            self.vlan_tag = int(vlan_string, base)
        except ValueError:
            raise ValidationError("Invalid VLAN tag: '%s'." % vlan_string)
        if self.vlan_tag <= 0 or self.vlan_tag >= 0xfff:
            raise ValidationError("VLAN tag out of range (1-4094).")

    def find_network(self):
        return Network.objects.get(vlan_tag=self.vlan_tag)


SPECIFIER_CLASSES = [NameSpecifier, IPSpecifier, VLANSpecifier]

SPECIFIER_TAGS = {
    spec_class.type_tag: spec_class
    for spec_class in SPECIFIER_CLASSES
}


def get_specifier_type(specifier):
    """Obtain the specifier class that knows how to parse `specifier`.

    :raise ValidationError: If `specifier` does not match any accepted type of
        network specifier.
    :return: A concrete `NetworkSpecifier` subclass that knows how to parse
        `specifier`.
    """
    if ':' in specifier:
        type_tag, _ = specifier.split(':', 1)
    else:
        type_tag = None
    specifier_class = SPECIFIER_TAGS.get(type_tag)
    if specifier_class is None:
        raise ValidationError(
            "Invalid network specifier type: '%s'." % type_tag)
    return specifier_class


def parse_network_spec(spec):
    """Parse a network specifier; return it as a `NetworkSpecifier` object.

    :raise ValidationError: If `spec` is malformed.
    """
    specifier_class = get_specifier_type(spec)
    return specifier_class(spec)


class NetworkManager(Manager):
    """Manager for :class:`Network` model class.

    Don't import or instantiate this directly; access as `<Class>.objects` on
    the model class it manages.
    """

    def get_from_spec(self, spec):
        """Find a single `Network` from a given network specifier.

        :raise ValidationError: If `spec` is malformed.
        :raise Network.DoesNotExist: If the network specifier does not match
            any known network.
        :return: The one `Network` matching `spec`.
        """
        specifier = parse_network_spec(spec)
        try:
            return specifier.find_network()
        except Network.DoesNotExist:
            raise Network.DoesNotExist("No network matching '%s'." % spec)


class Network(CleanSave, Model):

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    objects = NetworkManager()

    name = CharField(
        unique=True, blank=False, editable=True, max_length=255,
        validators=[NETWORK_NAME_VALIDATOR],
        help_text="Identifying name for this network.")

    ip = MAASIPAddressField(
        blank=False, editable=True, unique=True, null=False,
        help_text="Network address (e.g. 192.168.1.0).")

    netmask = MAASIPAddressField(
        blank=False, editable=True, null=False,
        help_text="Network mask (e.g. 255.255.255.0).")

    vlan_tag = PositiveSmallIntegerField(
        editable=True, null=True, blank=True, unique=True,
        help_text="A 12-bit field specifying the VLAN to which the frame "
                  "belongs. The hexadecimal values of 0x000 and 0xFFF "
                  "are reserved. All other values may be used as VLAN "
                  "identifiers, allowing up to 4,094 VLANs. The reserved "
                  "value 0x000 indicates that the frame does not belong "
                  "to any VLAN; in this case, the 802.1Q tag specifies "
                  "only a priority and is referred to as a priority tag. "
                  "On bridges, VLAN 1 (the default VLAN ID) is often "
                  "reserved for a management VLAN; this is vendor-"
                  "specific.")

    description = TextField(
        blank=True, editable=True,
        help_text="Any short description to help users identify the network")

    def get_network(self):
        """Return self as :class:`IPNetwork`.

        :raise AddrFormatError: If the combination of `self.ip` and
            `self.netmask` is a malformed network address.
        """
        return make_network(self.ip, self.netmask)

    def get_connected_nodes(self):
        """Return the `QuerySet` of the nodes connected to this network.

        :rtype: `django.db.models.query.QuerySet`
        """
        # Circular imports.
        from maasserver.models import Node
        return Node.objects.filter(
            macaddress__in=self.macaddress_set.all()).distinct()

    def __unicode__(self):
        net = unicode(self.get_network().cidr)
        # A vlan_tag of zero normalises to None.  But __unicode__ may be
        # called while we're not in a clean state, so handle zero as well.
        no_tag = [0, None]
        if self.vlan_tag in no_tag:
            tag = ''
        else:
            tag = '(tag:%x)' % self.vlan_tag
        return '%s:%s%s' % (self.name, net, tag)

    def clean_vlan_tag(self):
        """Validator for `vlan_tag`."""
        if self.vlan_tag is None:
            # Always OK.
            return
        if self.vlan_tag == 0xFFF:
            raise ValidationError(
                {'vlan_tag': ["Cannot use reserved value 0xFFF."]})
        if self.vlan_tag < 0 or self.vlan_tag > 0xFFF:
            raise ValidationError(
                {'vlan_tag':
                    ["Value must be between 0x000 and 0xFFF (12 bits)"]})

    def clean_netmask(self):
        """Validator for `vlan_tag`."""
        # Work out whether we're using IPv6 or v4. If we're using mixed
        # v6/v4 values, bail out.
        ip_address = IPAddress(self.ip)
        netmask_as_ip = IPAddress(self.netmask)
        if ip_address.version == 6 and netmask_as_ip.version == 6:
            check_ip = 'fc00:1:1::'
        elif ip_address.version == 4 and netmask_as_ip.version == 4:
            check_ip = '10.0.1.1'
        else:
            message = (
                "You can't mix IPv4 and IPv6 anywhere in the same network "
                "definition.")
            raise ValidationError({'netmask': [message]})

        try:
            # To see whether the netmask is well-formed, combine it with
            # an arbitrary valid IP address and see if IPNetwork's
            # constructor complains.
            make_network(check_ip, self.netmask)
        except AddrFormatError as e:
            raise ValidationError({'netmask': [e.message]})

        # We check netmask_as_ip.value here because there are two ways
        # to specify an "allow-all" netmask in IPv6, and it makes the if
        # statement unwieldy.
        if netmask_as_ip.value == 0:
            raise ValidationError(
                {'netmask': ["This netmask would span the entire Internet."]})
        full_netmask = (
            self.netmask == '255.255.255.255'
            or self.netmask == 'ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff')
        if full_netmask:
            raise ValidationError(
                {'netmask': ["This netmask leaves no room for IP addresses."]})

    def clean_fields(self, *args, **kwargs):
        super(Network, self).clean_fields(*args, **kwargs)
        self.clean_vlan_tag()
        self.clean_netmask()

    def clean(self):
        super(Network, self).clean()
        try:
            net = self.get_network()
        except AddrFormatError as e:
            # This probably means that the netmask was invalid, in which case
            # it will have its own error, but in case it isn't, we can't let
            # this slide.
            raise ValidationError("Invalid network address: %s" % e)
        # Normalise self.ip.  This strips off any host bits from the address.
        self.ip = unicode(net.cidr.ip)
        # Normalise self.vlan_tag.  A zero value ("not a VLAN") becomes None.
        if self.vlan_tag == 0:
            self.vlan_tag = None

    def validate_unique(self, exclude=None):
        super(Network, self).validate_unique(exclude=exclude)
        if exclude is None:
            exclude = []

        if 'ip' not in exclude and 'netmask' not in exclude:
            # The ip and netmask have passed validation.  Now see if they don't
            # clash with any other networks.
            my_net = self.get_network()
            for other in Network.objects.all().exclude(id=self.id):
                other_net = other.get_network()
                if my_net in other_net or other_net in my_net:
                    # This has to get an error dict, not a simple error string,
                    # or Django throws a fit (bug 1299114).
                    message = (
                        "IP range clashes with network '%s'." % other.name)
                    raise ValidationError({
                        'ip': [message],
                        'netmask': [message],
                        })
