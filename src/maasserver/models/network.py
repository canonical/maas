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


from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db.models import (
    CharField,
    GenericIPAddressField,
    Manager,
    Model,
    PositiveSmallIntegerField,
    )
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.utils.network import make_network
from netaddr import IPAddress
from netaddr.core import AddrFormatError

# Network name validator.  Must consist of alphanumerical characters and/or
# dashes.
NETWORK_NAME_VALIDATOR = RegexValidator('^[\w-]+$')


def parse_network_spec(spec):
    """Parse a network specifier; return its type and value.

    Networks can be identified by name, by an arbitrary IP address in the
    network (prefixed with `ip:`), or by a VLAN tag (prefixed with `vlan:`).

    :param spec: A string that should identify a network.
    :return: A tuple of the specifier's type (`name`, `ip`, or `vlan`) and the
        network's identifying value (a name, IP address, or numeric VLAN tag
        respectively).
    :raise ValidationError: If `spec` is malformed.
    """
    if ':' in spec:
        type_tag, value = spec.split(':', 1)
    else:
        type_tag, value = 'name', spec

    if type_tag == 'name':
        # Plain network name.  See that it really validates as one.
        NETWORK_NAME_VALIDATOR(spec)
    elif type_tag == 'ip':
        try:
            value = IPAddress(value)
        except AddrFormatError as e:
            raise ValidationError("Invalid IP address: %s." % e)
    elif type_tag == 'vlan':
        try:
            vlan_tag = int(value)
        except ValueError:
            raise ValidationError("Invalid VLAN tag: '%s'." % value)
        if vlan_tag <= 0 or vlan_tag >= 0xfff:
            raise ValidationError("VLAN tag out of range (1-4094).")
        value = vlan_tag
    else:
        raise ValidationError(
            "Invalid network specifier type: '%s'." % type_tag)
    return type_tag, value


class NetworkManager(Manager):
    """Manager for :class:`Network` model class.

    Don't import or instantiate this directly; access as `<Class>.objects` on
    the model class it manages.
    """

    def get_from_spec(self, spec):
        """Find a single `Network` from a given network specifier.

        A network specifier can be a network's name, or a prefix `ip:`
        followed by an IP address in the network's address range, or a prefix
        `vlan:` followed by a numerical (nonzero) VLAN tag.

        :raise ValidationError: If `spec` is malformed.
        :raise Network.DoesNotExist: If the network specifier does not match
            any known network.
        :return: The one `Network` matching `spec`.
        """
        type_tag, value = parse_network_spec(spec)
        try:
            if type_tag == 'name':
                return self.get(name=value)
            elif type_tag == 'ip':
                # Use self.all().  We could narrow down the database query,
                # but not a lot -- and this will cache better.  The number of
                # networks should not be so large that querying them from the
                # database becomes a problem for the region controller.
                for network in self.all():
                    if value in network.get_network():
                        # Networks don't overlap, so there can be only one.
                        return network
                raise Network.DoesNotExist()
            elif type_tag == 'vlan':
                return self.get(vlan_tag=value)
            else:
                # Should've been caught by parse_network_spec().
                raise AssertionError(
                    "Unhandled network specifier type '%s'" % type_tag)
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

    ip = GenericIPAddressField(
        blank=False, editable=True, unique=True, null=False,
        help_text="Network address (e.g. 192.168.1.0).")

    netmask = GenericIPAddressField(
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

    description = CharField(
        max_length=255, default='', blank=True, editable=True,
        help_text="Any short description to help users identify the network")

    def get_network(self):
        """Return self as :class:`IPNetwork`.

        :raise AddrFormatError: If the combination of `self.ip` and
            `self.netmask` is a malformed network address.
        """
        return make_network(self.ip, self.netmask)

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
        # To see whether the netmask is well-formed, combine it with an
        # arbitrary valid IP address and see if IPNetwork's constructor
        # complains.
        try:
            make_network('10.1.1.1', self.netmask)
        except AddrFormatError as e:
            raise ValidationError({'netmask': [e.message]})

        if self.netmask == '0.0.0.0':
            raise ValidationError(
                {'netmask': ["This netmask would span the entire Internet."]})
        if self.netmask == '255.255.255.255':
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
                    raise ValidationError(
                        "IP range clashes with network '%s'." % other.name)
