# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model definition for StaticIPAddress.

Contains all the in-use static IP addresses that are allocated by MAAS.
Generally speaking, these are written out to the DHCP server as "host"
blocks which will tie MACs into a specific IP.  The IPs are separate
from the dynamic range that the DHCP server itself allocates to unknown
clients.
"""

__all__ = [
    'StaticIPAddress',
]

from collections import defaultdict

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import (
    connection,
    IntegrityError,
    transaction,
)
from django.db.models import (
    ForeignKey,
    IntegerField,
    Manager,
    PROTECT,
    Q,
)
from maasserver import (
    DefaultMeta,
    locks,
)
from maasserver.enum import (
    INTERFACE_LINK_TYPE,
    INTERFACE_TYPE,
    IPADDRESS_FAMILY,
    IPADDRESS_TYPE,
    IPADDRESS_TYPE_CHOICES_DICT,
)
from maasserver.exceptions import (
    StaticIPAddressExhaustion,
    StaticIPAddressOutOfRange,
    StaticIPAddressUnavailable,
)
from maasserver.fields import MAASIPAddressField
from maasserver.models.cleansave import CleanSave
from maasserver.models.config import Config
from maasserver.models.domain import Domain
from maasserver.models.subnet import Subnet
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.dns import get_ip_based_hostname
from maasserver.utils.orm import (
    request_transaction_retry,
    transactional,
)
from maasserver.utils.threads import deferToDatabase
from netaddr import IPAddress
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils.enum import map_enum_reverse
from provisioningserver.utils.twisted import asynchronous


maaslog = get_maas_logger("node")


class HostnameIPMapping:
    """This is used to return address information for a host in a way that
       keeps life simple for the callers."""

    def __init__(
            self, system_id=None, ttl=None, ips: set=None, node_type=None):
        self.system_id = system_id
        self.node_type = node_type
        self.ttl = ttl
        self.ips = set() if ips is None else ips.copy()

    def __repr__(self):
        return "HostnameIPMapping(%r, %r, %r, %r)" % (
            self.system_id, self.ttl, self.ips, self.node_type)

    def __eq__(self, other):
        return self.__dict__ == other.__dict__


def convert_leases_to_dict(leases):
    """Convert a list of leases to a dictionary.

    :param leases: list of (ip, mac) tuples discovered from the leases table.
    :return: dict of {ip: [mac,...], ...} leases.
    """
    ip_leases = defaultdict(list)
    for ip, mac in leases:
        ip_leases[ip].append(mac)
    return ip_leases


class StaticIPAddressManager(Manager):
    """A utility to manage collections of IPAddresses."""

    def _verify_alloc_type(self, alloc_type, user=None):
        """Check validity of an `alloc_type` parameter when allocating.

        Also checks consistency with the `user` parameter.  If `user` is not
        `None`, then the allocation has to be `USER_RESERVED`, and vice versa.
        """
        if alloc_type not in [
                IPADDRESS_TYPE.AUTO,
                IPADDRESS_TYPE.STICKY,
                IPADDRESS_TYPE.USER_RESERVED,
                ]:
            raise ValueError(
                "IP address type %r is not allowed to use allocate_new." % (
                    alloc_type))

        if user is None:
            if alloc_type == IPADDRESS_TYPE.USER_RESERVED:
                raise AssertionError(
                    "Must provide user for USER_RESERVED alloc_type.")
        else:
            if alloc_type != IPADDRESS_TYPE.USER_RESERVED:
                raise AssertionError(
                    "Must not provide user for alloc_type other "
                    "than USER_RESERVED.")

    def _attempt_allocation(
            self, requested_address, alloc_type, user=None,
            subnet=None):
        """Attempt to allocate `requested_address`.

        All parameters must have been checked first.  This method relies on
        `IntegrityError` to detect addresses that are already in use, so
        nothing else must cause that error.

        Transaction model and isolation level have changed over time, and may
        do so again, so relying on database-level uniqueness validation is the
        most robust way we have of checking for clashes.

        :param requested_address: An `IPAddress` for the address that should
            be allocated.
        :param alloc_type: Allocation type.
        :param user: Optional user.
        :return: `StaticIPAddress` if successful.
        :raise StaticIPAddressUnavailable: if the address was already taken.
        """
        ipaddress = StaticIPAddress(
            ip=requested_address.format(), alloc_type=alloc_type,
            subnet=subnet)
        ipaddress.set_ip_address(requested_address.format())
        try:
            # Try to save this address to the database. Do this in a nested
            # transaction so that we can continue using the outer transaction
            # even if this breaks.
            with transaction.atomic():
                ipaddress.save()
        except IntegrityError:
            # The address is already taken.
            raise StaticIPAddressUnavailable(
                "The IP address %s is already in use." %
                requested_address.format())
        else:
            # We deliberately do *not* save the user until now because it
            # might result in an IntegrityError, and we rely on the latter
            # in the code above to indicate an already allocated IP
            # address and nothing else.
            ipaddress.user = user
            ipaddress.save()
            return ipaddress

    def allocate_new(
            self, subnet=None, alloc_type=IPADDRESS_TYPE.AUTO, user=None,
            requested_address=None, exclude_addresses=[]):
        """Return a new StaticIPAddress.

        :param subnet: The subnet from which to allocate the address.
        :param alloc_type: What sort of IP address to allocate in the
            range of choice in IPADDRESS_TYPE.
        :param user: If providing a user, the alloc_type must be
            IPADDRESS_TYPE.USER_RESERVED. Conversely, if the alloc_type is
            IPADDRESS_TYPE.USER_RESERVED the user must also be provided.
            AssertionError is raised if these conditions are not met.
        :param requested_address: Optional IP address that the caller wishes
            to use instead of being allocated one at random.
        :param exclude_addresses: A list of addresses which MUST NOT be used.

        All IP parameters can be strings or netaddr.IPAddress.

        Note that this method has been designed to work even when the database
        is running with READ COMMITTED isolation. Try to keep it that way.
        """
        # This check for `alloc_type` is important for later on. We rely on
        # detecting IntegrityError as a sign than an IP address is already
        # taken, and so we must first eliminate all other possible causes.
        self._verify_alloc_type(alloc_type, user)

        if subnet is None:
            if requested_address:
                subnet = Subnet.objects.get_best_subnet_for_ip(
                    requested_address)
            else:
                raise StaticIPAddressOutOfRange(
                    "Could not find an appropriate subnet.")

        if requested_address is None:
            with locks.staticip_acquire:
                requested_address = self._async_find_free_ip(
                    subnet, exclude_addresses=exclude_addresses).wait(30)
                try:
                    return self._attempt_allocation(
                        requested_address, alloc_type, user,
                        subnet=subnet)
                except StaticIPAddressUnavailable:
                    # We lost the race: another transaction has taken this IP
                    # address. Retry this transaction from the top.
                    request_transaction_retry()
        else:
            requested_address = IPAddress(requested_address)
            subnet.validate_static_ip(requested_address)
            return self._attempt_allocation(
                requested_address, alloc_type,
                user=user, subnet=subnet)

    def _get_user_reserved_mappings(self, domain_or_subnet, raw_ttl=False):
        # A poorly named routine these days, since it actually returns
        # addresses for anything with any DNSResource records as well.
        default_ttl = Config.objects.get_config('default_dns_ttl')
        qs = self.filter(
            Q(alloc_type=IPADDRESS_TYPE.USER_RESERVED) |
            Q(dnsresource__isnull=False))
        # If this is a subnet, we need to ignore subnet.id, as per
        # get_hostname_ip_mapping().  LP#1600259
        if isinstance(domain_or_subnet, Subnet):
            pass
        elif isinstance(domain_or_subnet, Domain):
            qs = qs.filter(dnsresource__domain_id=domain_or_subnet.id)
        qs = qs.prefetch_related("dnsresource_set")
        mappings = defaultdict(HostnameIPMapping)
        for instance in qs:
            ip = instance.ip
            rrset = instance.dnsresource_set.all()
            # 2016-01-20 LaMontJones N.B.:
            # Empirically, for dnsrr in instance.dnsresource_set.all(): ...
            # else: with a non-empty rrset yields both the for loop AND the
            # else clause.  Wrapping it all in a if/else: avoids that issue.
            if rrset.count() > 0:
                for dnsrr in rrset:
                    if dnsrr.name is None or dnsrr.name == '':
                        hostname = get_ip_based_hostname(ip)
                        hostname = "%s.%s" % (
                            get_ip_based_hostname(ip),
                            Domain.objects.get_default_domain().name)
                    else:
                        hostname = '%s.%s' % (dnsrr.name, dnsrr.domain.name)
                    if raw_ttl or dnsrr.address_ttl is not None:
                        ttl = dnsrr.address_ttl
                    elif dnsrr.domain.ttl is not None:
                        ttl = dnsrr.domain.ttl
                    else:
                        ttl = default_ttl
                    mappings[hostname].ttl = ttl
                    mappings[hostname].ips.add(ip)
            else:
                # No DNSResource, but it's USER_RESERVED.
                domain = Domain.objects.get_default_domain()
                hostname = "%s.%s" % (get_ip_based_hostname(ip), domain.name)
                if raw_ttl or domain.ttl is not None:
                    ttl = domain.ttl
                else:
                    ttl = default_ttl
                mappings[hostname].ttl = ttl
                mappings[hostname].ips.add(ip)
        return mappings

    @asynchronous
    def _async_find_free_ip(self, *args, **kwargs):
        return deferToDatabase(
            transactional(self._find_free_ip), *args, **kwargs)

    def _find_free_ip(self, subnet, exclude_addresses=[]):
        """Helper function that finds a free IP address using a lock."""
        # The purpose of sorting here is so that we ensure we always get an
        # IP address from the *smallest* free contiguous range. This way,
        # larger ranges can be preserved in case they need to be used for
        # applications requiring them.
        free_ranges = sorted(list(
            subnet.get_ipranges_not_in_use(
                exclude_addresses=exclude_addresses)
            ), key=lambda x: x.num_addresses)
        if len(free_ranges) == 0:
            raise StaticIPAddressExhaustion(
                "No more IPs available in subnet: %s" % subnet.cidr)
        return str(IPAddress(free_ranges[0].first))

    def get_hostname_ip_mapping(self, domain_or_subnet, raw_ttl=False):
        """Return hostname mappings for `StaticIPAddress` entries.

        Returns a mapping `{hostnames -> (ttl, [ips])}` corresponding to
        current `StaticIPAddress` objects for the nodes in `domain`, or
        `subnet`.

        At most one IPv4 address and one IPv6 address will be returned per
        node, each the one for whichever `Interface` was created first.

        The returned name is an FQDN (no trailing dot.)
        """
        cursor = connection.cursor()

        # DISTINCT ON returns the first matching row for any given
        # hostname, using the query's ordering.  Here, we're trying to
        # return the IPs for the oldest Interface address.
        #
        # For nodes that have disable_ipv4 set, leave out any IPv4 address.
        default_ttl = "%d" % Config.objects.get_config('default_dns_ttl')
        if raw_ttl:
            ttl_clause = """node.address_ttl"""
        else:
            ttl_clause = """
                COALESCE(
                    node.address_ttl,
                    domain.ttl,
                    %s)""" % default_ttl
        sql_query = """
            SELECT DISTINCT ON (node.hostname, is_boot, family(staticip.ip))
                CONCAT(node.hostname, '.', domain.name) AS fqdn,
                node.system_id,
                node.node_type,
                """ + ttl_clause + """ AS ttl,
                staticip.ip,
                COALESCE(
                    node.boot_interface_id IS NOT NULL AND
                    (
                        node.boot_interface_id = interface.id OR
                        node.boot_interface_id = parent.id
                    ),
                    False
                ) as is_boot
            FROM
                maasserver_interface AS interface
            LEFT OUTER JOIN maasserver_interfacerelationship AS rel ON
                interface.id = rel.child_id
            LEFT OUTER JOIN maasserver_interface AS parent ON
                rel.parent_id = parent.id
            JOIN maasserver_node AS node ON
                node.id = interface.node_id
            JOIN maasserver_domain as domain ON
                domain.id = node.domain_id
            JOIN maasserver_interface_ip_addresses AS link ON
                link.interface_id = interface.id
            JOIN maasserver_staticipaddress AS staticip ON
                staticip.id = link.staticipaddress_id
            """
        if isinstance(domain_or_subnet, Domain):
            # The model has nodes in the parent domain, but they actually live
            # in the child domain.  And the parent needs the glue.  So we
            # return such nodes addresses in _BOTH_ the parent and the child
            # domains. domain2.name will be non-null if this host's fqdn is the
            # name of a domain in MAAS.
            sql_query += """
            LEFT JOIN maasserver_domain as domain2 ON
                /* Pick up another copy of domain looking for instances of
                 * nodes a the top of a domain.
                 */
                domain2.name = CONCAT(node.hostname, '.', domain.name)
            WHERE
                (domain2.name IS NOT NULL OR node.domain_id = %s) AND
            """
            query_parms = [domain_or_subnet.id, ]
        else:
            # For subnets, we need ALL the names, so that we can correctly
            # identify which ones should have the FQDN.  dns/zonegenerator.py
            # optimizes based on this, and only calls once with a subnet,
            # expecting to get all the subnets back in one table.
            sql_query += """
            WHERE
            """
            query_parms = []
        sql_query += """
                staticip.ip IS NOT NULL AND
                host(staticip.ip) != '' AND
                (
                    node.disable_ipv4 IS FALSE OR
                    family(staticip.ip) <> 4
                )
            ORDER BY
                node.hostname,
                is_boot DESC,
                family(staticip.ip),
                CASE
                    WHEN interface.type = 'bond' AND
                        parent.id = node.boot_interface_id THEN 1
                    WHEN interface.type = 'physical' AND
                        interface.id = node.boot_interface_id THEN 2
                    WHEN interface.type = 'bond' THEN 3
                    WHEN interface.type = 'physical' THEN 4
                    WHEN interface.type = 'vlan' THEN 5
                    WHEN interface.type = 'alias' THEN 6
                    WHEN interface.type = 'unknown' THEN 7
                    ELSE 8
                END,
                /*
                 * We want STICKY and USER_RESERVED addresses to be preferred,
                 * followed by AUTO, DHCP, and finally DISCOVERED.
                 */
                CASE
                    WHEN staticip.alloc_type = 1 /* STICKY */
                        THEN 1
                    WHEN staticip.alloc_type = 4 /* USER_RESERVED */
                        THEN 2
                    WHEN staticip.alloc_type = 0 /* AUTO */
                        THEN 3
                    WHEN staticip.alloc_type = 5 /* DHCP */
                        THEN 4
                    WHEN staticip.alloc_type = 6 /* DISCOVERED */
                        THEN 5
                    ELSE staticip.alloc_type
                END,
                interface.id
            """
        iface_sql_query = """
            SELECT
                CONCAT(node.hostname, '.', domain.name) AS fqdn,
                node.system_id,
                node.node_type,
                """ + ttl_clause + """ AS ttl,
                staticip.ip,
                interface.name
            FROM
                maasserver_interface AS interface
            JOIN maasserver_node AS node ON
                node.id = interface.node_id
            JOIN maasserver_domain as domain ON
                domain.id = node.domain_id
            JOIN maasserver_interface_ip_addresses AS link ON
                link.interface_id = interface.id
            JOIN maasserver_staticipaddress AS staticip ON
                staticip.id = link.staticipaddress_id
            """
        if isinstance(domain_or_subnet, Domain):
            # This logic is similar to the logic in sql_query above.
            iface_sql_query += """
            LEFT JOIN maasserver_domain as domain2 ON
                /* Pick up another copy of domain looking for instances of
                 * the name as the top of a domain.
                 */
                domain2.name = CONCAT(
                    interface.name, '.', node.hostname, '.', domain.name)
            WHERE
                (domain2.name IS NOT NULL OR node.domain_id = %s) AND
            """
        else:
            # For subnets, we need ALL the names, so that we can correctly
            # identify which ones should have the FQDN.  dns/zonegenerator.py
            # optimizes based on this, and only calls once with a subnet,
            # expecting to get all the subnets back in one table.
            iface_sql_query += """
            WHERE
            """
        iface_sql_query += """
                staticip.ip IS NOT NULL AND
                host(staticip.ip) != '' AND
                (
                    node.disable_ipv4 IS FALSE OR
                    family(staticip.ip) <> 4
                )
            ORDER BY
                node.hostname,
                interface.id
            """
        # We get user reserved et al mappings first, so that we can overwrite
        # TTL as we process the return from the SQL horror above.
        mapping = self._get_user_reserved_mappings(domain_or_subnet)
        # All of the mappings that we got mean that we will only want to add
        # addresses for the boot interface (is_boot == True).
        iface_is_boot = defaultdict(bool, {
            hostname: True for hostname in mapping.keys()
        })
        cursor.execute(sql_query, query_parms)
        # The records from the query provide, for each hostname (after
        # stripping domain), the boot and non-boot interface ip address in ipv4
        # and ipv6.  Our task: if there are boot interace IPs, they win.  If
        # there are none, then whatever we got wins.  The ORDER BY means that
        # we will see all of the boot interfaces before we see any non-boot
        # interface IPs.  See Bug#1584850
        for (fqdn, system_id, node_type, ttl,
                ip, is_boot) in cursor.fetchall():
            mapping[fqdn].node_type = node_type
            mapping[fqdn].system_id = system_id
            mapping[fqdn].ttl = ttl
            if is_boot:
                iface_is_boot[fqdn] = True
            # If we have an IP on the right interface type, save it.
            if is_boot == iface_is_boot[fqdn]:
                mapping[fqdn].ips.add(ip)
        # Next, get all the addresses, on all the interfaces, and add the ones
        # that are not already present on the FQDN as $IFACE.$FQDN.
        cursor.execute(iface_sql_query, (domain_or_subnet.id,))
        for (fqdn, system_id, node_type, ttl,
                ip, iface_name) in cursor.fetchall():
            if ip not in mapping[fqdn].ips:
                name = "%s.%s" % (iface_name, fqdn)
                mapping[name].node_type = node_type
                mapping[name].system_id = system_id
                mapping[name].ttl = ttl
                mapping[name].ips.add(ip)
        return mapping

    def filter_by_ip_family(self, family):
        possible_families = map_enum_reverse(IPADDRESS_FAMILY)
        if family not in possible_families:
            raise ValueError(
                "IP address family %r is not a member of "
                "IPADDRESS_FAMILY." % family)
        return self.extra(
            where=["family(maasserver_staticipaddress.ip) = %s"],
            params=[family],
        )

    def filter_by_subnet_cidr_family(self, family):
        possible_families = map_enum_reverse(IPADDRESS_FAMILY)
        if family not in possible_families:
            raise ValueError(
                "Subnet CIDR family %r is not a member of "
                "IPADDRESS_FAMILY." % family)
        return self.extra(
            tables=["maasserver_subnet"], where=[
                "maasserver_staticipaddress.subnet_id = maasserver_subnet.id",
                "family(maasserver_subnet.cidr) = %s",
            ], params=[family])


class StaticIPAddress(CleanSave, TimestampedModel):

    class Meta(DefaultMeta):
        verbose_name = "Static IP Address"
        verbose_name_plural = "Static IP Addresses"

    # IP can be none when a DHCP lease has expired: in this case the entry
    # in the StaticIPAddress only materializes the connection between an
    # interface and a subnet.
    ip = MAASIPAddressField(
        unique=True, null=True, editable=False, blank=True,
        default=None, verbose_name='IP')

    alloc_type = IntegerField(
        editable=False, null=False, blank=False, default=IPADDRESS_TYPE.AUTO)

    # Subnet is only null for IP addresses allocate before the new networking
    # model.
    subnet = ForeignKey('Subnet', editable=True, blank=True, null=True)

    user = ForeignKey(
        User, default=None, blank=True, null=True, editable=False,
        on_delete=PROTECT)

    # Used only by DISCOVERED address to set the lease_time for an active
    # lease. Time is in seconds.
    lease_time = IntegerField(
        default=0, editable=False, null=False, blank=False)

    objects = StaticIPAddressManager()

    def __str__(self):
        # Attempt to show the symbolic alloc_type name if possible.
        type_names = map_enum_reverse(IPADDRESS_TYPE)
        strtype = type_names.get(self.alloc_type, '%s' % self.alloc_type)
        return "%s:type=%s" % (self.ip, strtype)

    def get_node(self):
        """Return the Node of the first Interface connected to this IP
        address."""
        interface = self.get_interface()
        if interface is not None:
            return interface.get_node()
        else:
            return None

    def get_interface(self):
        """Return the first Interface connected to this IP address."""
        # Note that, while this relationship is modeled as a many-to-many,
        # MAAS currently only relates a single interface per IP address
        # at this time. In the future, we may want to model virtual IPs, in
        # which case this will need to change.
        interface = self.interface_set.first()
        return interface

    def get_interface_link_type(self):
        """Return the `INTERFACE_LINK_TYPE`."""
        if self.alloc_type == IPADDRESS_TYPE.AUTO:
            return INTERFACE_LINK_TYPE.AUTO
        elif self.alloc_type == IPADDRESS_TYPE.DHCP:
            return INTERFACE_LINK_TYPE.DHCP
        elif self.alloc_type == IPADDRESS_TYPE.USER_RESERVED:
            return INTERFACE_LINK_TYPE.STATIC
        elif self.alloc_type == IPADDRESS_TYPE.STICKY:
            if not self.ip:
                return INTERFACE_LINK_TYPE.LINK_UP
            else:
                return INTERFACE_LINK_TYPE.STATIC
        else:
            raise ValueError("Unknown alloc_type.")

    def get_log_name_for_alloc_type(self):
        """Return a nice log name for the `alloc_type` of the IP address."""
        return IPADDRESS_TYPE_CHOICES_DICT[self.alloc_type]

    def is_linked_to_one_unknown_interface(self):
        """Return True if the IP address is only linked to one unknown
        interface."""
        interface_types = [
            interface.type
            for interface in self.interface_set.all()
        ]
        return interface_types == [INTERFACE_TYPE.UNKNOWN]

    def get_related_discovered_ip(self):
        """Return the related DISCOVERED IP address for this IP address. This
        comes from looking at the DISCOVERED IP addresses assigned to the
        related interfaces.
        """
        interfaces = list(self.interface_set.all())
        discovered_ips = [
            ip
            for ip in StaticIPAddress.objects.filter(
                interface__in=interfaces,
                alloc_type=IPADDRESS_TYPE.DISCOVERED,
                ip__isnull=False).order_by('-id')
            if ip.ip
        ]
        if len(discovered_ips) > 0:
            return discovered_ips[0]
        else:
            return None

    def get_ip(self):
        """Return the IP address assigned."""
        ip, subnet = self.get_ip_and_subnet()
        return ip

    def get_ip_and_subnet(self):
        """Return the IP address and subnet assigned.

        For all alloc_types except DHCP it returns `ip` and `subnet`. When
        `alloc_type` is DHCP it returns the associated DISCOVERED `ip` and
        `subnet` on the same linked interfaces.
        """
        if self.alloc_type == IPADDRESS_TYPE.DHCP:
            discovered_ip = self.get_related_discovered_ip()
            if discovered_ip is not None:
                return discovered_ip.ip, discovered_ip.subnet
        return self.ip, self.subnet

    def deallocate(self):
        """Mark this IP address as no longer in use.
        After return, this object is no longer valid.
        """
        self.delete()

    def clean_subnet_and_ip_consistent(self):
        """Validate that the IP address is inside the subnet."""

        # USER_RESERVED addresses must have an IP address specified.
        # Blank AUTO, STICKY and DHCP addresses have a special meaning:
        # - Blank AUTO addresses mean the interface will get an IP address
        #   auto assigned when it goes to be deployed.
        # - Blank STICKY addresses mean the interface should come up and be
        #   associated with a particular Subnet, but no IP address should
        #   be assigned.
        # - DHCP IP addresses are always blank. The model will look for
        #   a DISCOVERED IP address on the same interface to map to the DHCP
        #   IP address with `get_ip()`.
        if self.alloc_type == IPADDRESS_TYPE.USER_RESERVED:
            if not self.ip:
                raise ValidationError(
                    {'ip': ["IP address must be specified."]})
        if self.alloc_type == IPADDRESS_TYPE.DHCP:
            if self.ip:
                raise ValidationError(
                    {'ip': ["IP address must not be specified."]})

        if self.ip and self.subnet and self.subnet.cidr:
            address = self.get_ipaddress()
            network = self.subnet.get_ipnetwork()
            if address not in network:
                raise ValidationError(
                    {'ip': ["IP address %s is not within the subnet: %s."
                            % (str(address), str(network))]})

    def get_ipaddress(self):
        """Returns this StaticIPAddress wrapped in an IPAddress object.

        :return: An IPAddress, (or None, if the IP address is unspecified)
        """
        if self.ip:
            return IPAddress(self.ip)
        else:
            return None

    def get_mac_addresses(self):
        """Return set of all MAC's linked to this ip."""
        return set(
            interface.mac_address
            for interface in self.interface_set.all()
        )

    def clean(self, *args, **kwargs):
        super(StaticIPAddress, self).clean(*args, **kwargs)
        self.clean_subnet_and_ip_consistent()

    def full_clean(self, exclude=None, validate_unique=False):
        """Overrides Django's default for validating unique columns.

        Django's ORM has a misfeature: `Model.full_clean` -- which our
        CleanSave mix-in calls -- checks every unique key against the database
        before actually saving the row. Django runs READ COMMITTED by default,
        which means there's a racey period between the uniqueness validation
        check and the actual insert.

        Here we disable this misfeature so that we will get `IntegrityError`
        alone from trying to insert a duplicate key. We also save a query or
        two. We could consider disabling this misfeature globally.
        """
        return super(StaticIPAddress, self).full_clean(
            exclude=exclude, validate_unique=validate_unique)

    def _set_subnet(self, subnet, interfaces=None):
        """Resets the Subnet for this StaticIPAddress, making sure to update
        the VLAN for a related Interface (if the VLAN has changed).
        """
        self.subnet = subnet
        if interfaces is not None:
            for iface in interfaces:
                if (iface is not None and subnet is not None and
                        iface.vlan_id != subnet.vlan_id):
                    iface.vlan = subnet.vlan
                    iface.save()

    def render_json(self, with_username=False, with_node_summary=False):
        """Render a representation of this `StaticIPAddress` object suitable
        for converting to JSON. Includes optional parameters wherever a join
        would be implied by including a specific piece of information."""
        # Circular imports.
        # XXX mpontillo 2016-03-11 we should do the formatting client side.
        from maasserver.websockets.base import dehydrate_datetime
        data = {
            "ip": self.ip,
            "alloc_type": self.alloc_type,
            "created": dehydrate_datetime(self.created),
            "updated": dehydrate_datetime(self.updated),
        }
        if with_username and self.user is not None:
            data["user"] = self.user.username
        if with_node_summary:
            iface = self.get_interface()
            node = self.get_node()
            if node is not None:
                data["node_summary"] = {
                    "system_id": node.system_id,
                    "node_type": node.node_type,
                    "fqdn": node.fqdn,
                    "hostname": node.hostname,
                }
                if iface is not None:
                    data["node_summary"]["via"] = iface.get_name()
                if (with_username and
                        self.alloc_type != IPADDRESS_TYPE.DISCOVERED):
                    # If a user owns this node, overwrite any username we found
                    # earlier. A node's owner takes precedence.
                    if node.owner and node.owner.username:
                        data["user"] = node.owner.username
        return data

    def set_ip_address(self, ipaddr, iface=None):
        """Sets the IP address to the specified value, and also updates
        the subnet field.

        The new subnet is determined by calling get_best_subnet_for_ip() on
        the SubnetManager.

        If an interface is supplied, the Interface's VLAN is also updated
        to match the VLAN of the new Subnet.
        """
        self.ip = ipaddr

        # Cases we need to handle:
        # (0) IP address is being cleared out (remains within Subnet)
        # (1) IP address changes to another address within the same Subnet
        # (2) IP address changes to another address with a different Subnet
        # (3) IP address changes to an address within an unknown Subnet

        if not ipaddr:
            # (0) Nothing to be done. We're clearing out the IP address.
            return

        if self.ip and self.subnet:
            if self.get_ipaddress() in self.subnet.get_ipnetwork():
                # (1) Nothing to be done. Already in an appropriate Subnet.
                return
            else:
                # (2) and (3): the Subnet has changed (could be to None)
                subnet = Subnet.objects.get_best_subnet_for_ip(ipaddr)
                # We must save here, otherwise it's possible that we can't
                # traverse the interface_set many-to-many.
                self.save()
                self._set_subnet(subnet, interfaces=self.interface_set.all())
