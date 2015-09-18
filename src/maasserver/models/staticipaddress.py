# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model definition for StaticIPAddress.

Contains all the in-use static IP addresses that are allocated by MAAS.
Generally speaking, these are written out to the DHCP server as "host"
blocks which will tie MACs into a specific IP.  The IPs are separate
from the dynamic range that the DHCP server itself allocates to unknown
clients.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

str = None

__metaclass__ = type
__all__ = [
    'StaticIPAddress',
]

from collections import defaultdict

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import (
    connection,
    IntegrityError,
)
from django.db.models import (
    CharField,
    ForeignKey,
    IntegerField,
    Manager,
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
from maasserver.models.subnet import Subnet
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils import strip_domain
from maasserver.utils.dns import (
    get_ip_based_hostname,
    validate_hostname,
)
from maasserver.utils.orm import (
    make_serialization_failure,
    transactional,
)
from netaddr import (
    IPAddress,
    IPRange,
)
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils.enum import map_enum_reverse
from provisioningserver.utils.twisted import asynchronous
from twisted.internet.threads import deferToThread


maaslog = get_maas_logger("node")


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
            hostname=None, subnet=None):
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
            hostname=hostname, subnet=subnet)
        ipaddress.set_ip_address(requested_address.format())
        try:
            # Try to save this address to the database.
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
            self, network, static_range_low, static_range_high,
            dynamic_range_low, dynamic_range_high,
            alloc_type=IPADDRESS_TYPE.AUTO, user=None,
            requested_address=None, hostname=None, subnet=None,
            exclude_addresses=[]):
        """Return a new StaticIPAddress.

        :param network: The network the address should be allocated in.
        :param static_range_low: The lowest static address to allocate in a
            range. Used if `requested_address` is not passed.
        :param static_range_high: The highest static address to allocate in a
            range. Used if `requested_address` is not passed.
        :param dynamic_range_low: The lowest dynamic address. Used if
            `requested_address` is passed, check that its not inside the
            dynamic range.
        :param dynamic_range_high: The highest dynamic address. Used if
            `requested_address` is passed, check that its not inside the
            dynamic range.
        :param alloc_type: What sort of IP address to allocate in the
            range of choice in IPADDRESS_TYPE.
        :param user: If providing a user, the alloc_type must be
            IPADDRESS_TYPE.USER_RESERVED. Conversely, if the alloc_type is
            IPADDRESS_TYPE.USER_RESERVED the user must also be provided.
            AssertionError is raised if these conditions are not met.
        :param requested_address: Optional IP address that the caller wishes
            to use instead of being allocated one at random.

        All IP parameters can be strings or netaddr.IPAddress.

        Note that this method has been designed to work even when the database
        is running with READ COMMITTED isolation. Try to keep it that way.
        """
        # This check for `alloc_type` is important for later on. We rely on
        # detecting IntegrityError as a sign than an IP address is already
        # taken, and so we must first eliminate all other possible causes.
        self._verify_alloc_type(alloc_type, user)

        # XXX 2015-09-01 mpontillo: We added a subnet= parameter to this
        # method, but overlooked the fact that a 'network' is passed in.
        # This was possibly done because a Subnet is less ambiguous, but
        # it still needs to be cleaned up.
        # XXX:fabric - this method has problems with overlapping subnets.
        # If the user didn't specify a Subnet, look for the best possible
        # match. First start with any explicitly-requested address. Then
        # fall back to looking at the ranges (if specified).
        if subnet is None and requested_address:
            subnet = Subnet.objects.get_best_subnet_for_ip(
                requested_address)
        elif subnet is None and static_range_low:
            subnet = Subnet.objects.get_best_subnet_for_ip(
                static_range_low)
        elif subnet is None and dynamic_range_low:
            subnet = Subnet.objects.get_best_subnet_for_ip(
                dynamic_range_low)

        if requested_address is None:
            static_range_low = IPAddress(static_range_low)
            static_range_high = IPAddress(static_range_high)
            static_range = IPRange(static_range_low, static_range_high)

            with locks.staticip_acquire:
                requested_address = self._async_find_free_ip(
                    static_range_low, static_range_high, static_range,
                    alloc_type, user,
                    exclude_addresses=exclude_addresses).wait(30)
                try:
                    return self._attempt_allocation(
                        requested_address, alloc_type, user,
                        hostname=hostname, subnet=subnet)
                except StaticIPAddressUnavailable:
                    # This is phantom read: another transaction has
                    # taken this IP.  Raise a serialization failure to
                    # let the retry mechanism do its thing.
                    raise make_serialization_failure()
        else:
            dynamic_range_low = IPAddress(dynamic_range_low)
            dynamic_range_high = IPAddress(dynamic_range_high)
            dynamic_range = IPRange(dynamic_range_low, dynamic_range_high)

            requested_address = IPAddress(requested_address)
            if requested_address not in network:
                raise StaticIPAddressOutOfRange(
                    "%s is not inside the network %s" % (
                        requested_address.format(), network))
            if requested_address in dynamic_range:
                raise StaticIPAddressOutOfRange(
                    "%s is inside the dynamic range %s to %s" % (
                        requested_address.format(), dynamic_range_low.format(),
                        dynamic_range_high.format()))
            return self._attempt_allocation(
                requested_address, alloc_type,
                user=user, hostname=hostname, subnet=subnet)

    def _get_user_reserved_mappings(self):
        mappings = []
        for mapping in self.filter(alloc_type=IPADDRESS_TYPE.USER_RESERVED):
            hostname = mapping.hostname
            ip = mapping.ip
            if hostname is None or hostname == '':
                hostname = get_ip_based_hostname(ip)
            mappings.append((hostname, ip))
        return mappings

    @asynchronous
    def _async_find_free_ip(self, *args, **kwargs):
        return deferToThread(
            transactional(self._find_free_ip), *args, **kwargs)

    def _find_free_ip(
            self, range_low, range_high, static_range, alloc_type,
            user, exclude_addresses):
        """Helper function that finds a free IP address using a lock."""
        # The set of _allocated_ addresses in the range is going to be
        # smaller or at least no bigger than the set of addresses in the
        # whole range, so we materialise a Python set of only allocated
        # addreses. We can iterate through `static_range` without
        # materialising every address within. This is critical for IPv6,
        # where ranges may contain 2^64 addresses without blinking.
        existing = self.filter(
            ip__gte=range_low.format(),
            ip__lte=range_high.format(),
        )
        # We might consider limiting this query, but that's premature. If
        # MAAS is managing even as many as 10k nodes in a single network
        # then my hat is most certainly on the menu. However, we do care
        # only about the IP address field here.
        existing = existing.values_list("ip", flat=True)
        # Now materialise the set.
        existing = {IPAddress(ip) for ip in existing}
        existing = existing.union({
            IPAddress(exclude)
            for exclude in exclude_addresses
            })
        # Now find the first free address in the range.
        for requested_address in static_range:
            if requested_address not in existing:
                return requested_address
        else:
            raise StaticIPAddressExhaustion(
                "No more IPs available in range %s-%s" % (
                    range_low.format(), range_high.format()))

    def get_hostname_ip_mapping(self, nodegroup):
        """Return hostname mappings for `StaticIPAddress` entries.

        Returns a mapping `{hostnames -> [ips]}` corresponding to current
        `StaticIPAddress` objects for the nodes in `nodegroup`.

        At most one IPv4 address and one IPv6 address will be returned per
        node, each the one for whichever `Interface` was created first.

        Any domain will be stripped from the hostnames.
        """
        cursor = connection.cursor()

        # DISTINCT ON returns the first matching row for any given
        # hostname, using the query's ordering.  Here, we're trying to
        # return the IP for the oldest Interface address.
        #
        # For nodes that have disable_ipv4 set, leave out any IPv4 address.
        cursor.execute("""
            SELECT DISTINCT ON (node.hostname, family(staticip.ip))
                node.hostname, staticip.ip
            FROM maasserver_interface AS interface
            JOIN maasserver_node AS node ON
                node.id = interface.node_id
            JOIN maasserver_interface_ip_addresses AS link ON
                link.interface_id = interface.id
            JOIN maasserver_staticipaddress AS staticip ON
                staticip.id = link.staticipaddress_id
            WHERE
                staticip.ip IS NOT NULL AND
                host(staticip.ip) != '' AND
                node.nodegroup_id = %s AND
                (
                    node.disable_ipv4 IS FALSE OR
                    family(staticip.ip) <> 4
                )
            ORDER BY
                node.hostname,
                family(staticip.ip),
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
                CASE
                    WHEN interface.type = 'bond' THEN 1
                    WHEN interface.type = 'physical' THEN 2
                    WHEN interface.type = 'vlan' THEN 3
                    WHEN interface.type = 'alias' THEN 4
                    WHEN interface.type = 'unknown' THEN 5
                    ELSE 6
                END,
                interface.id
            """, (nodegroup.id,))
        mapping = defaultdict(list)
        for hostname, ip in cursor.fetchall():
            hostname = strip_domain(hostname)
            mapping[hostname].append(ip)
        for hostname, ip in self._get_user_reserved_mappings():
            hostname = strip_domain(hostname)
            mapping[hostname].append(ip)
        return mapping

    def _clean_discovered_ip_addresses_on_interface(
            self, interface, subnet_family, dont_delete=[]):
        # Clean the current DISCOVERED IP addresses linked to this interface.
        old_discovered = StaticIPAddress.objects.filter_by_subnet_cidr_family(
            subnet_family)
        old_discovered = old_discovered.filter(
            interface=interface, alloc_type=IPADDRESS_TYPE.DISCOVERED)
        old_discovered = old_discovered.prefetch_related('interface_set')
        old_discovered = list(old_discovered)
        dont_delete_ids = [ip.id for ip in dont_delete]
        for old_ip in old_discovered:
            interfaces = list(old_ip.interface_set.all())
            delete_ip = (
                old_ip.id not in dont_delete_ids
            )
            if delete_ip:
                if interfaces == [interface]:
                    # Only the passed interface is connected to this
                    # DISCOVERED IP address so we can just delete the IP
                    # address.
                    old_ip.delete()
                else:
                    # More than one is connected so we need to clear just
                    # remove the link.
                    interface.ip_addresses.remove(old_ip)

    def update_leases(self, nodegroup, leases):
        """Refresh our knowledge of a `nodegroup`'s IP mappings.

        This deletes entries that are no longer current, adds new ones,
        and updates or replaces ones that have changed.
        This method also updates the Interface objects to link them to
        their respective cluster interface.

        :param nodegroup: The nodegroup that these updates are for.
        :param leases: A list describing all current IP/MAC mappings as
            managed by the node group's DHCP server: [ (ip, mac), ...].
            Any :class:`StaticIPAddress` entries for `nodegroup` that are from
            DISCOVERED not in `leases` will be deleted.
        :return: Iterable of IP addresses that were newly leased.
        """
        # Circular imports.
        from maasserver.models.interface import (
            Interface,
            UnknownInterface,
            )

        # Current DISCOVERED addresses attached to the NodeGroup
        # we're updating.
        discoved_ips = StaticIPAddress.objects.filter(
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
            subnet__nodegroupinterface__nodegroup=nodegroup)
        ip_leases = convert_leases_to_dict(leases)
        discoved_ips = discoved_ips.prefetch_related('interface_set')
        discoved_ips = {
            unicode(ip.ip): ip
            for ip in discoved_ips
        }

        # Update all the DISCOVERED allocations for the lease information.
        mac_leases = defaultdict(list)
        subnet = None
        for ipaddr, mac_list in ip_leases.viewitems():
            # So we don't make a query for every IP address we check to see if
            # the IP address is in the same subnet from the previous IP.
            if subnet is None:
                subnet = Subnet.objects.get_best_subnet_for_ip(ipaddr)
            elif IPAddress(ipaddr) not in subnet.get_ipnetwork():
                subnet = Subnet.objects.get_best_subnet_for_ip(ipaddr)
            subnet_family = subnet.get_ipnetwork().version

            # If the ipaddr is not in the dynamic range for the cluster
            # interface then it is ignored. Address that match this criteria
            # are hostmaps set on the clusters DHCP server.
            ngi = subnet.get_managed_cluster_interface()
            if IPAddress(ipaddr) not in ngi.get_dynamic_ip_range():
                continue

            # Get current DISCOVERED ip address or create a new one.
            ipaddress = discoved_ips.pop(ipaddr, None)
            if ipaddress is not None:
                # All interfaces attached to the IP address that are not the
                # current MAC address should be set to another IP address. This
                # makes sure that those interfaces does not lose its link to
                # their last subnet.
                other_interfaces = list(
                    ipaddress.interface_set.exclude(mac_address__in=mac_list))
                if len(other_interfaces) > 0:
                    # Get or create an empty DISCOVERED IP address for these
                    # other interfaces, linked to the old subnet.
                    empty_ip, _ = StaticIPAddress.objects.get_or_create(
                        alloc_type=IPADDRESS_TYPE.DISCOVERED, ip=None,
                        subnet=ipaddress.subnet)
                    for other_interface in other_interfaces:
                        other_interface.ip_addresses.remove(ipaddress)
                        other_interface.ip_addresses.add(empty_ip)

                # Update the subnet on the exist IP address to make sure its
                # the correct subnet.
                ipaddress.subnet = subnet
                ipaddress.save()
            else:
                # This is a new IP address
                ipaddress = StaticIPAddress.objects.create(
                    alloc_type=IPADDRESS_TYPE.DISCOVERED, ip=ipaddr,
                    subnet=subnet)
            for mac in mac_list:
                mac_leases[mac].append(ipaddress)

            # Update the DISCOVERED IP address for the interfaces with MAC
            # address.
            for mac in mac_list:
                interfaces = list(
                    Interface.objects.filter(mac_address=mac))
                if len(interfaces) > 0:
                    for interface in interfaces:
                        # XXX 09-04-2015 blake_r: We assume that an interface
                        # is on the same VLAN as the subnet. It would be nice
                        # to figure out which one to fix but it is currently
                        # not possible based on the lease information received.
                        if interface.vlan_id == subnet.vlan_id:
                            # Remove any extra DISCOVERED address on the
                            # interface as it should only ever have one per IP
                            # family.
                            self._clean_discovered_ip_addresses_on_interface(
                                interface, subnet_family,
                                dont_delete=mac_leases[mac])
                            # Add the newly discovered address to the
                            # interface.
                            interface.ip_addresses.add(ipaddress)
                else:
                    # Unknown MAC address so create an unknown interface for
                    # this MAC address.
                    unknown_interface = UnknownInterface(
                        name="eth0", mac_address=mac, vlan_id=subnet.vlan_id)
                    unknown_interface.save()
                    unknown_interface.ip_addresses.add(ipaddress)

        # Reload all the extra DISCOVERED IP addresses that are no longer
        # leased so the information can be cleared. This is reloaded just to
        # make sure the information is current from all of the lease updating
        # above.
        olds_ids = [
            old_ip.id
            for old_ip in discoved_ips.values()
        ]
        discoved_ips = StaticIPAddress.objects.filter(id__in=olds_ids)
        for old_ip in discoved_ips:
            if old_ip.is_linked_to_one_unknown_interface():
                # IP address is linked to an unknown interface so the interface
                # and the IP address is no longer needed.
                for interface in old_ip.interface_set.all():
                    interface.delete(remove_ip_address=False)
                old_ip.delete()
            elif len(old_ip.interface_set.all()) == 0:
                # This IP address has not linked interfaces so it should
                # be removed as well.
                old_ip.delete()
            else:
                # This IP address is linked to a known interface, just clear
                # its IP to keep the link to the subnet available.
                old_ip.ip = None
                old_ip.save()

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

    # XXX: removing the null=True here causes dozens of tests to fail with
    # NOT NULL constraint violations. (an empty string an NULL should mean
    # the same thing here.)
    hostname = CharField(
        max_length=255, default='', blank=True, unique=False, null=True,
        validators=[validate_hostname])

    user = ForeignKey(
        User, default=None, blank=True, null=True, editable=False)

    objects = StaticIPAddressManager()

    def __unicode__(self):
        # Attempt to show the symbolic alloc_type name if possible.
        type_names = map_enum_reverse(IPADDRESS_TYPE)
        strtype = type_names.get(self.alloc_type, '%s' % self.alloc_type)
        return "%s:type=%s" % (self.ip, strtype)

    def get_node(self):
        """Return the Node of the first interface connected to this IP
        address."""
        interface = self.interface_set.first()
        if interface is not None:
            return interface.get_node()
        else:
            return None

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
                            % (unicode(address), unicode(network))]})

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
                self._set_subnet(subnet, interfaces=self.interface_set.all())
