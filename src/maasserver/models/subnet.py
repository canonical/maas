# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for subnets."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

str = None

__metaclass__ = type
__all__ = [
    'create_cidr',
    'Subnet',
]


from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db.models import (
    CharField,
    ForeignKey,
    Manager,
    PROTECT,
)
from djorm_pgarray.fields import ArrayField
from maasserver import DefaultMeta
from maasserver.fields import (
    CIDRField,
    MAASIPAddressField,
)
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from netaddr import (
    IPAddress,
    IPNetwork,
)


SUBNET_NAME_VALIDATOR = RegexValidator('^[.: \w/-]+$')


def get_default_vlan():
    from maasserver.models.vlan import VLAN
    return VLAN.objects.get_default_vlan()


def create_cidr(network, subnet_mask=None):
    """Given the specified network and subnet mask, create a CIDR string.

    Discards any extra bits present in the 'network'. (bits which overlap
    zeroes in the netmask)

    Returns the object in unicode format, so that this function can be used
    in database migrations (which do not support custom fields).

    :param network:The network
    :param subnet_mask:An IPv4 or IPv6 netmask or prefix length
    :return:An IPNetwork representing the CIDR.
    """
    if type(network) == IPNetwork:
        if not subnet_mask:
            subnet_mask = network.netmask
        network = network.network
    elif type(network) == IPAddress:
        if subnet_mask and type(subnet_mask) is not IPAddress:
            subnet_mask = IPAddress(subnet_mask)

    cidr = IPNetwork(unicode(network) + '/' + unicode(subnet_mask)).cidr
    return unicode(cidr)


class SubnetManager(Manager):
    """Manager for :class:`Subnet` model."""

    def create_from_cidr(self, cidr, vlan, space):
        """Create a subnet from the given CIDR."""
        name = "subnet-" + unicode(cidr)
        return self.create(name=name, cidr=cidr, vlan=vlan, space=space)

    # Note: << is the postgresql "is contained within" operator.
    # See http://www.postgresql.org/docs/8.4/static/functions-net.html
    # Use an ORDER BY and LIMIT clause to match the most specific
    # subnet for the given IP address.
    find_subnet_with_ip_query = """
        SELECT subnet.*
        FROM maasserver_subnet AS subnet
            WHERE %s << subnet.cidr
            ORDER BY masklen(subnet.cidr) DESC
            LIMIT 1
        """

    def get_subnet_with_ip(self, ip):
        """Find the most specific Subnet the specified IP address belongs in.
        """
        subnets = self.raw(
            self.find_subnet_with_ip_query, params=[unicode(ip)])

        for subnet in subnets:
            return subnet  # This is stable because the query is ordered.
        else:
            return None


class Subnet(CleanSave, TimestampedModel):

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""
        unique_together = (
            ('name', 'space'),
        )

    objects = SubnetManager()

    name = CharField(
        blank=False, editable=True, max_length=255,
        validators=[SUBNET_NAME_VALIDATOR],
        help_text="Identifying name for this subnet.")

    vlan = ForeignKey(
        'VLAN', default=get_default_vlan, editable=True, blank=False,
        null=False, on_delete=PROTECT)

    space = ForeignKey(
        'Space', editable=True, blank=False, null=False, on_delete=PROTECT)

    # XXX:fabric: unique constraint should be relaxed once proper support for
    # fabrics is implemented. The CIDR must be unique withing a Fabric, not
    # globally unique.
    cidr = CIDRField(
        blank=False, unique=True, editable=True, null=False)

    gateway_ip = MAASIPAddressField(blank=True, editable=True, null=True)

    dns_servers = ArrayField(
        dbtype="text", blank=True, editable=True, null=True, default=[])

    def get_cidr(self):
        return IPNetwork(self.cidr)

    def __unicode__(self):
        return "name=%s vlan.vid=%s, cidr=%s" % (
            self.name, self.vlan.vid, self.cidr)

    def validate_gateway_ip(self):
        if self.gateway_ip is None or self.gateway_ip == '':
            return
        gateway_addr = IPAddress(self.gateway_ip)
        if gateway_addr not in self.get_cidr():
            message = "Gateway IP must be within CIDR range."
            raise ValidationError({'gateway_ip': [message]})

    def clean(self, *args, **kwargs):
        self.validate_gateway_ip()
