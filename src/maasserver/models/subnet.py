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


from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from django.core.validators import RegexValidator
from django.db.models import (
    CharField,
    ForeignKey,
    Manager,
    PROTECT,
)
from django.shortcuts import get_object_or_404
from djorm_pgarray.fields import ArrayField
from maasserver import DefaultMeta
from maasserver.enum import (
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
)
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

    find_subnets_with_ip_query = """
        SELECT DISTINCT subnet.*, masklen(subnet.cidr) "prefixlen"
        FROM
            maasserver_subnet AS subnet
        WHERE
            %s << subnet.cidr
        ORDER BY prefixlen DESC
        """

    def get_subnets_with_ip(self, ip):
        """Find the most specific Subnet the specified IP address belongs in.
        """
        return self.raw(
            self.find_subnets_with_ip_query, params=[unicode(ip)])

    # Note: << is the postgresql "is contained within" operator.
    # See http://www.postgresql.org/docs/8.4/static/functions-net.html
    # Use an ORDER BY and LIMIT clause to match the most specific
    # subnet for the given IP address.
    # Also, when using "SELECT DISTINCT", the items in ORDER BY must be
    # present in the SELECT. (hence the extra field)
    find_best_subnet_for_ip_query = """
        SELECT DISTINCT
            subnet.*,
            masklen(subnet.cidr) "prefixlen",
            ngi.management "ngi_mgmt",
            nodegroup.status "nodegroup_status"
        FROM maasserver_subnet AS subnet
        LEFT OUTER JOIN maasserver_nodegroupinterface AS ngi
            ON ngi.subnet_id = subnet.id
        INNER JOIN maasserver_vlan AS vlan
            ON subnet.vlan_id = vlan.id
        LEFT OUTER JOIN maasserver_nodegroup AS nodegroup
          ON ngi.nodegroup_id = nodegroup.id
        WHERE
            %s << subnet.cidr AND /* Specified IP is inside range */
            vlan.fabric_id = %s
        ORDER BY
            /* For nodegroup_status, 1=ENABLED, 2=DISABLED, and NULL
               means the outer join didn't find a related NodeGroup. */
            nodegroup_status NULLS LAST,
            /* For ngi_mgmt, higher numbers indicate "more management".
               (and NULL indicates lack of a related NodeGroupInterface. */
            ngi_mgmt DESC NULLS LAST,
            /* If there are multiple (or no) subnets related to a NodeGroup,
               we'll want to pick the most specific one that the IP address
               falls within. */
            prefixlen DESC
        LIMIT 1
        """

    def get_best_subnet_for_ip(self, ip, fabric=None):
        """Find the most-specific managed Subnet the specified IP address
        belongs to.

        The most-specific Subnet is a Subnet that is both referred to by
        a managed, active NodeGroupInterface, and on the specified Fabric.

        If no Fabric is specified, uses the default Fabric.
        """
        # Circular imports
        fabric = self._find_fabric(fabric)

        subnets = self.raw(
            self.find_best_subnet_for_ip_query,
            params=[unicode(ip), fabric])

        for subnet in subnets:
            return subnet  # This is stable because the query is ordered.
        else:
            return None

    def _find_fabric(self, fabric):
        from maasserver.models import Fabric

        if fabric is None:
            # If no Fabric is specified, use the default. (will always be 0)
            fabric = 0
        elif isinstance(fabric, Fabric):
            fabric = fabric.id
        else:
            fabric = int(fabric)
        return fabric

    def get_subnet_or_404(self, id, user, perm):
        """Fetch a `Subnet` by its id.  Raise exceptions if no `Subnet` with
        this id exists or if the provided user has not the required permission
        to access this `Subnet`.

        :param id: The subnet_id.
        :type id: int
        :param user: The user that should be used in the permission check.
        :type user: django.contrib.auth.models.User
        :param perm: The permission to assert that the user has on the node.
        :type perm: unicode
        :raises: django.http.Http404_,
            :class:`maasserver.exceptions.PermissionDenied`.

        .. _django.http.Http404: https://
           docs.djangoproject.com/en/dev/topics/http/views/
           #the-http404-exception
        """
        subnet = get_object_or_404(self.model, id=id)
        if user.has_perm(perm, subnet):
            return subnet
        else:
            raise PermissionDenied()


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

    def get_ipnetwork(self):
        return IPNetwork(self.cidr)

    def get_ip_version(self):
        return self.get_ipnetwork().version

    def update_cidr(self, cidr):
        cidr = unicode(cidr)
        # If the old name had the CIDR embedded in it, update that first.
        if self.name:
            self.name = self.name.replace(unicode(self.cidr), cidr)
        else:
            self.name = cidr
        self.cidr = cidr

    def __unicode__(self):
        return "%s:%s(vid=%s)" % (
            self.name, self.cidr, self.vlan.vid)

    def validate_gateway_ip(self):
        if self.gateway_ip is None or self.gateway_ip == '':
            return
        gateway_addr = IPAddress(self.gateway_ip)
        if gateway_addr not in self.get_ipnetwork():
            message = "Gateway IP must be within CIDR range."
            raise ValidationError({'gateway_ip': [message]})

    def get_managed_cluster_interface(self):
        """Return the cluster interface that manages this subnet."""
        interfaces = self.nodegroupinterface_set.filter(
            nodegroup__status=NODEGROUP_STATUS.ENABLED)
        interfaces = interfaces.exclude(
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        return interfaces.first()

    def clean(self, *args, **kwargs):
        self.validate_gateway_ip()

    def get_cluster_interfaces(self):
        """Returns a `QuerySet` of NodeGroupInterface objects which may
        manage this subnet."""
        # Circular imports
        from maasserver.models import NodeGroupInterface
        return NodeGroupInterface.objects.filter(subnet=self)

    def get_managed_cluster_interfaces(self):
        """Returns a `QuerySet` of managed NodeGroupInterface objects for
        this subnet."""
        return self.get_cluster_interfaces().exclude(
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
