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
    ]


from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db.models import (
    CharField,
    GenericIPAddressField,
    Model,
    PositiveSmallIntegerField,
    )
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from netaddr import IPNetwork
from netaddr.core import AddrFormatError

# Network name validator.  Must consist of alphanumerical characters and/or
# dashes.
NETWORK_NAME_VALIDATOR = RegexValidator('^[\w-]+$')


class Network(CleanSave, Model):

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

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
        editable=True, blank=False, unique=True,
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
        # Careful: IPNetwork(ip, netmask) will _seem_ to work, but the second
        # argument does not get interpreted as the netmask!  Instead it gets
        # accepted as a boolean that affects how to pick a default netmask.
        # Testing may not show it, unless you try it with a different netmask
        # than is the default for your base IP address.
        return IPNetwork('%s/%s' % (self.ip, self.netmask))

    def __unicode__(self):
        net = unicode(self.get_network().cidr)
        if self.vlan_tag == 0:
            return net
        else:
            return "%s(tag:%x)" % (net, self.vlan_tag)

    def clean_vlan_tag(self):
        """Validator for `vlan_tag`."""
        if self.vlan_tag == 0xFFF:
            raise ValidationError(
                {'tag': ["Cannot use reserved value 0xFFF."]})
        if self.vlan_tag < 0 or self.vlan_tag > 0xFFF:
            raise ValidationError(
                {'tag': ["Value must be between 0x000 and 0xFFF (12 bits)"]})

    def clean_netmask(self):
        """Validator for `vlan_tag`."""
        # To see whether the netmask is well-formed, combine it with an
        # arbitrary valid IP address and see if IPNetwork's constructor
        # complains.
        sample_cidr = '10.1.1.1/%s' % self.netmask
        try:
            IPNetwork(sample_cidr)
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

    def validate_unique(self, exclude=None):
        super(Network, self).validate_unique(exclude=exclude)
        if exclude is None:
            exclude = []

        if 'ip' not in exclude and 'netmask' not in exclude:
            # The ip and netmask have passed validation.  Now see if they don't
            # clash with any other networks.
            my_net = self.get_network()
            for other in Network.objects.all().exclude(name=self.name):
                other_net = other.get_network()
                if my_net in other_net or other_net in my_net:
                    raise ValidationError(
                        "IP range clashes with network '%s'." % other.name)
