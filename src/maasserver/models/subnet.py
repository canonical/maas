# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for subnets."""
from maasserver.enum import IPRANGE_TYPE


__all__ = [
    'create_cidr',
    'Subnet',
]


from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from django.core.validators import RegexValidator
from django.db.models import (
    CharField,
    ForeignKey,
    IntegerField,
    Manager,
    PROTECT,
    Q,
    TextField,
)
from django.db.models.query import QuerySet
from maasserver import DefaultMeta
from maasserver.enum import (
    RDNS_MODE,
    RDNS_MODE_CHOICES,
)
from maasserver.fields import (
    CIDRField,
    MAASIPAddressField,
)
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.orm import MAASQueriesMixin
from netaddr import (
    AddrFormatError,
    IPAddress,
    IPNetwork,
)
from provisioningserver.utils.network import (
    MAASIPSet,
    make_ipaddress,
    make_iprange,
    parse_integer,
)

# Note: since subnets can be referenced in the API by name, if this regex is
# updated, then the regex in urls_api.py also needs to be udpated.
SUBNET_NAME_VALIDATOR = RegexValidator('^[.: \w/-]+$')


def get_default_vlan():
    from maasserver.models.vlan import VLAN
    return VLAN.objects.get_default_vlan().id


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
    if isinstance(network, IPNetwork) and subnet_mask is None:
        return str(network.cidr)
    else:
        network = make_ipaddress(network)
    if subnet_mask is None and isinstance(network, (bytes, str)):
        if '/' in network:
            return str(IPNetwork(network).cidr)
        else:
            assert False, "Network passed as CIDR string must contain '/'."
    network = str(make_ipaddress(network))
    if isinstance(subnet_mask, int):
        mask = str(subnet_mask)
    else:
        mask = str(make_ipaddress(subnet_mask))
    cidr = IPNetwork(network + '/' + mask).cidr
    return str(cidr)


class SubnetQueriesMixin(MAASQueriesMixin):

    find_subnets_with_ip_query = """
        SELECT DISTINCT subnet.*, masklen(subnet.cidr) "prefixlen"
        FROM
            maasserver_subnet AS subnet
        WHERE
            %s << subnet.cidr
        ORDER BY prefixlen DESC
        """

    def raw_subnets_containing_ip(self, ip):
        """Find the most specific Subnet the specified IP address belongs in.
        """
        return self.raw(
            self.find_subnets_with_ip_query, params=[str(ip)])

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
            vlan.dhcp_on "dhcp_on"
        FROM maasserver_subnet AS subnet
        INNER JOIN maasserver_vlan AS vlan
            ON subnet.vlan_id = vlan.id
        WHERE
            %s << subnet.cidr /* Specified IP is inside range */
        ORDER BY
            /* Pick subnet that is on a VLAN that is managed over a subnet
               that is not managed on a VLAN. */
            dhcp_on DESC,
            /* If there are multiple subnets we want to pick the most specific
               one that the IP address falls within. */
            prefixlen DESC
        LIMIT 1
        """

    def get_best_subnet_for_ip(self, ip):
        """Find the most-specific managed Subnet the specified IP address
        belongs to."""
        subnets = self.raw(
            self.find_best_subnet_for_ip_query,
            params=[str(ip)])

        for subnet in subnets:
            return subnet  # This is stable because the query is ordered.
        else:
            return None

    def validate_filter_specifiers(self, specifiers):
        """Validate the given filter string."""
        try:
            self.filter_by_specifiers(specifiers)
        except (ValueError, AddrFormatError) as e:
            raise ValidationError(e.message)

    def get_specifiers_q(self, specifiers, separator=':', **kwargs):
        """Returns a Q object for objects matching the given specifiers.

        Allows a number of types to be prefixed in front of each specifier:
            * 'ip:' Matches the subnet that best matches the given IP address.
            * 'cidr:' Matches a subnet with the exact given CIDR.
            * 'name': Matches a subnet with the given name.
            * 'vid:' Matches a subnet whose VLAN has the given VID.
                Can be used with a hexadecimal or binary string by prefixing
                it with '0x' or '0b'.
            ' 'vlan:' Synonym for 'vid' for compatibility with older MAAS
                versions.
            * 'space:' Matches the name of this subnet's space.

        If no specifier is given, the input will be treated as a CIDR. If
        the input is not a valid CIDR, it will be treated as subnet name.

        :raise:AddrFormatError:If a specific IP address or CIDR is requested,
            but the address could not be parsed.

        :return:django.db.models.Q
        """
        # Circular imports.
        from maasserver.models import (
            Fabric,
            Interface,
            Space,
            VLAN,
        )

        # This dict is used by the constraints code to identify objects
        # with particular properties. Please note that changing the keys here
        # can impact backward compatibility, so use caution.
        specifier_types = {
            None: self._add_default_query,
            'cidr': self._add_unvalidated_cidr_query,
            'fabric': (Fabric.objects, 'vlan__subnet'),
            'id': self._add_subnet_id_query,
            'interface': (Interface.objects, 'ip_addresses__subnet'),
            'ip': self._add_ip_in_subnet_query,
            'name': "__name",
            'space': (Space.objects, 'subnet'),
            'vid': self._add_vlan_vid_query,
            'vlan': (VLAN.objects, 'subnet'),
        }
        return super(SubnetQueriesMixin, self).get_specifiers_q(
            specifiers, specifier_types=specifier_types, separator=separator,
            **kwargs)

    def _add_default_query(self, current_q, op, item):
        """If the item we're matching is an integer, first try to locate the
        subnet by its ID. Otherwise, try to parse it as a CIDR. If all else
        fails, search by the name.
        """
        id = self.get_object_id(item)
        if id is not None:
            return op(current_q, Q(id=id))

        try:
            ip = IPNetwork(item)
        except (AddrFormatError, ValueError):
            # The user didn't pass in a valid CIDR, so try the subnet name.
            return op(current_q, Q(name=item))
        else:
            cidr = str(ip.cidr)
            return op(current_q, Q(cidr=cidr))

    def _add_unvalidated_cidr_query(self, current_q, op, item):
        ip = IPNetwork(item)
        cidr = str(ip.cidr)
        current_q = op(current_q, Q(cidr=cidr))
        return current_q

    def _add_ip_in_subnet_query(self, current_q, op, item):
        # Try to validate this before it hits the database, since this
        # is going to be a raw query.
        item = str(IPAddress(item))
        # This is a special case. If a specific IP filter is included,
        # a custom query is needed to get the result. We can't chain
        # a raw query using Q without grabbing the IDs first.
        ids = self.get_id_list(self.raw_subnets_containing_ip(item))
        current_q = op(current_q, Q(id__in=ids))
        return current_q

    def _add_subnet_id_query(self, current_q, op, item):
        try:
            item = parse_integer(item)
        except ValueError:
            raise ValidationError("Subnet ID must be numeric.")
        else:
            current_q = op(current_q, Q(id=item))
            return current_q


class SubnetQuerySet(QuerySet, SubnetQueriesMixin):
    """Custom QuerySet which mixes in some additional queries specific to
    subnets. This needs to be a mixin because an identical method is needed on
    both the Manager and all QuerySets which result from calling the manager.
    """


class SubnetManager(Manager, SubnetQueriesMixin):
    """Manager for :class:`Subnet` model."""

    def get_queryset(self):
        queryset = SubnetQuerySet(self.model, using=self._db)
        return queryset

    def create_from_cidr(self, cidr, vlan=None, space=None):
        """Create a subnet from the given CIDR."""
        name = "subnet-" + str(cidr)
        from maasserver.models import (Space, VLAN)
        if space is None:
            space = Space.objects.get_default_space()
        if vlan is None:
            vlan = VLAN.objects.get_default_vlan()
        return self.create(name=name, cidr=cidr, vlan=vlan, space=space)

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

    def get_subnet_or_404(self, specifiers, user, perm):
        """Fetch a `Subnet` by its id.  Raise exceptions if no `Subnet` with
        this id exists or if the provided user has not the required permission
        to access this `Subnet`.

        :param specifiers: A specifier to uniquely locate the Subnet.
        :type specifiers: unicode
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
        subnet = self.get_object_by_specifiers_or_raise(specifiers)
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

    rdns_mode = IntegerField(
        choices=RDNS_MODE_CHOICES, editable=True,
        default=RDNS_MODE.DEFAULT)

    gateway_ip = MAASIPAddressField(blank=True, editable=True, null=True)

    dns_servers = ArrayField(
        TextField(), blank=True, editable=True, null=True, default=list)

    def get_ipnetwork(self):
        return IPNetwork(self.cidr)

    def get_ip_version(self):
        return self.get_ipnetwork().version

    def update_cidr(self, cidr):
        cidr = str(cidr)
        # If the old name had the CIDR embedded in it, update that first.
        if self.name:
            self.name = self.name.replace(str(self.cidr), cidr)
        else:
            self.name = cidr
        self.cidr = cidr

    def __str__(self):
        return "%s:%s(vid=%s)" % (
            self.name, self.cidr, self.vlan.vid)

    def validate_gateway_ip(self):
        if self.gateway_ip is None or self.gateway_ip == '':
            return
        gateway_addr = IPAddress(self.gateway_ip)
        if gateway_addr not in self.get_ipnetwork():
            message = "Gateway IP must be within CIDR range."
            raise ValidationError({'gateway_ip': [message]})

    def clean(self, *args, **kwargs):
        self.validate_gateway_ip()

    def get_staticipaddresses_in_use(self):
        """Returns a list of `netaddr.IPAddress` objects to represent each
        IP address in use in this `Subnet`."""
        # We could exclude DISCOVERED addresses here, but that wouldn't be
        # genuine. (we'd be allowing something we have observed as an in-use
        # address to potentially be claimed for something else, which could
        # be a conflict.)
        # Note, the original implementation used .exclude() to filter,
        # but we'll filter at runtime so that prefetch_related in the
        # websocket works properly.
        return set(
            IPAddress(ip.ip)
            for ip in self.staticipaddress_set.all()
            if ip.ip)

    def get_ipranges_in_use(self):
        """Returns a `MAASIPSet` of `MAASIPRange` objects which are currently
        in use on this `Subnet`."""
        ranges = set()
        assigned_ip_addresses = self.get_staticipaddresses_in_use()
        ranges |= set(
            make_iprange(ip, purpose="assigned-ip")
            for ip in assigned_ip_addresses
        )
        for iprange in self.get_dynamic_ranges():
            ranges |= set(iprange.get_MAASIPRange())
        ranges |= self.get_reserved_maasipset()
        return MAASIPSet(ranges)

    def get_ipranges_not_in_use(self):
        """Returns a `MAASIPSet` of ranges which are currently free on this
        `Subnet`."""
        ranges = self.get_ipranges_in_use()
        return ranges.get_unused_ranges(self.get_ipnetwork())

    def get_iprange_usage(self):
        """Returns both the reserved and unreserved IP ranges in this Subnet.
        (This prevents a potential race condition that could occur if an IP
        address is allocated or deallocated between calls.)

        :returns: A tuple indicating the (reserved, unreserved) ranges."""
        reserved_ranges = self.get_ipranges_in_use()
        return reserved_ranges.get_full_range(self.get_ipnetwork())

    def render_json_for_related_ips(
            self, with_username=True, with_node_summary=True):
        """Render a representation of this subnet's related IP addresses,
        suitable for converting to JSON. Optionally exclude user and node
        information."""
        return sorted([
            ip.render_json(
                with_username=with_username,
                with_node_summary=with_node_summary)
            for ip in self.staticipaddress_set.all()
            if ip.ip
            ], key=lambda json: IPAddress(json['ip']))

    def get_dynamic_ranges(self):
        return self.iprange_set.filter(
            type__in=[IPRANGE_TYPE.MANAGED_DHCP, IPRANGE_TYPE.UNMANAGED_DHCP])

    def get_static_ranges(self):
        # XXX mpontillo 2016-01-07: this needs to be deprecated in favor of
        # assuming the entire range is static
        return self.iprange_set.filter(type=IPRANGE_TYPE.MANAGED_STATIC)

    def get_admin_reserved_ranges(self):
        return self.iprange_set.filter(type=IPRANGE_TYPE.ADMIN_RESERVED)

    def get_user_reserved_ranges(self):
        return self.iprange_set.filter(type=IPRANGE_TYPE.USER_RESERVED)

    def is_valid_static_ip(self, ip):
        for iprange in self.get_static_ranges():
            if ip in iprange.netaddr_iprange:
                return True
        return False

    def get_reserved_maasipset(self):
        # XXX mpontillo 2016-01-21: migrate static ranges to their opposite
        # admin-reserved so this is no longer necessary.
        static_ranges = set(
            iprange.get_MAASIPRange()
            for iprange in self.get_static_ranges())
        if len(static_ranges) > 0:
            reserved_ranges = MAASIPSet(static_ranges).get_unused_ranges(
                self.cidr, comment="reserved")
        else:
            reserved_ranges = MAASIPSet([])
        reserved_ranges |= MAASIPSet(
            iprange.get_MAASIPRange()
            for iprange in self.get_admin_reserved_ranges()
        )
        # XXX mpontillo 2016-01-21: need to determine how to deal with user
        # reserved ranges. For now, exclude them all.
        reserved_ranges |= MAASIPSet(
            iprange.get_MAASIPRange()
            for iprange in self.get_user_reserved_ranges()
        )
        return reserved_ranges

    def get_dynamic_range_for_ip(self, ip):
        """Return `IPRange` for the provided `ip`."""
        # XXX mpontillo 2016-01-21: for some reason this query doesn't work.
        # I tried it both like this, and with:
        #     start_ip__gte=ip, and end_ip__lte=ip
        # return get_one(self.get_dynamic_ranges().extra(
        #        where=["start_ip >= inet '%s'" % ip,
        # ... which sounds a lot like comment 15 in:
        #     https://code.djangoproject.com/ticket/11442
        for iprange in self.get_dynamic_ranges():
            if ip in iprange.netaddr_iprange:
                return iprange
        return None
