# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model definition for StaticIPAddress.

Contains all the in-use static IP addresses that are allocated by MAAS.
Generally speaking, these are written out to the DHCP server as "host"
blocks which will tie MACs into a specific IP.  The IPs are separate
from the dynamic range that the DHCP server itself allocates to unknown
clients.
"""
from collections import defaultdict, namedtuple
from dataclasses import dataclass, field
from queue import Empty, Queue
import threading
from typing import Dict, Iterable, Optional, Set, TypeVar

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import connection, IntegrityError, transaction
from django.db.models import (
    CASCADE,
    DateTimeField,
    F,
    ForeignKey,
    Func,
    GenericIPAddressField,
    IntegerField,
    Manager,
    PROTECT,
    Q,
    UniqueConstraint,
    Value,
)
from netaddr import IPAddress

from maasserver import locks
from maasserver.enum import (
    INTERFACE_LINK_TYPE,
    INTERFACE_TYPE,
    IPADDRESS_FAMILY,
    IPADDRESS_TYPE,
    IPADDRESS_TYPE_CHOICES_DICT,
)
from maasserver.exceptions import (
    StaticIPAddressOutOfRange,
    StaticIPAddressUnavailable,
)
from maasserver.models.cleansave import CleanSave
from maasserver.models.config import Config
from maasserver.models.domain import Domain
from maasserver.models.subnet import Subnet
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils import orm
from maasserver.utils.dns import (
    get_iface_name_based_hostname,
    get_ip_based_hostname,
)
from provisioningserver.utils.enum import map_enum_reverse

StaticIPAddress = TypeVar("StaticIPAddress")

_mapping_base_fields = (
    "fqdn",
    "system_id",
    "node_type",
    "user_id",
    "ttl",
    "ip",
)

_special_mapping_result = _mapping_base_fields + ("dnsresource_id",)

_mapping_query_result = _mapping_base_fields + (
    "is_boot",
    "preference",
    "family",
)

_interface_mapping_result = _mapping_base_fields + ("iface_name", "assigned")

SpecialMappingQueryResult = namedtuple(
    "SpecialMappingQueryResult", _special_mapping_result
)

MappingQueryResult = namedtuple("MappingQueryResult", _mapping_query_result)

InterfaceMappingResult = namedtuple(
    "InterfaceMappingResult", _interface_mapping_result
)


class HostnameIPMapping:
    """This is used to return address information for a host in a way that
    keeps life simple for the callers."""

    def __init__(
        self,
        system_id=None,
        ttl=None,
        ips: set = None,
        node_type=None,
        dnsresource_id=None,
        user_id=None,
    ):
        self.system_id = system_id
        self.node_type = node_type
        self.ttl = ttl
        self.ips = set() if ips is None else ips.copy()
        self.dnsresource_id = dnsresource_id
        self.user_id = user_id

    def __repr__(self):
        return "HostnameIPMapping({!r}, {!r}, {!r}, {!r}, {!r}, {!r})".format(
            self.system_id,
            self.ttl,
            self.ips,
            self.node_type,
            self.dnsresource_id,
            self.user_id,
        )

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


@dataclass
class SubnetAllocationQueue:
    pool: Queue[str] = field(default_factory=Queue)
    reserved: Set[str] = field(default_factory=set)
    pending: int = 0

    def get(self) -> str:
        return self.pool.get_nowait()

    def fill(self, addresses: Iterable[str]):
        for addr in addresses:
            self.pool.put(addr)

    def reserve(self, address: str):
        self.reserved.add(address)

    def free(self, address: str):
        self.reserved.remove(address)

    def get_reserved(self, extra: Iterable[str]) -> Iterable[str]:
        return self.reserved.union(extra)


class FreeIPAddress:
    pool: Dict[str, SubnetAllocationQueue] = {}
    counter_lock = threading.Lock()
    pool_lock = threading.Lock()

    def __init__(self, subnet: Subnet, exclude: Optional[Iterable] = None):
        self._subnet = subnet
        self._free_ip = None
        self._exclude = exclude or []
        with FreeIPAddress.pool_lock:
            self.queue = FreeIPAddress.pool.setdefault(
                str(subnet), SubnetAllocationQueue()
            )

    def __enter__(self) -> str:
        while self._free_ip is None:
            try:
                ip = self.queue.get()
            except Empty:
                self._fill_pool()
            else:
                if ip not in self._exclude:
                    self._free_ip = ip
        self.queue.reserve(self._free_ip)
        return self._free_ip

    def __exit__(self, *_):
        self.queue.free(self._free_ip)

    def _update_counter(self, adj: int):
        with FreeIPAddress.counter_lock:
            self.queue.pending += adj

    def _fill_pool(self):
        self._update_counter(1)
        with FreeIPAddress.pool_lock:
            pending = self.queue.pending
            assert pending >= 0
            if pending > 0:
                excl = self.queue.get_reserved(self._exclude)
                addresses = self._subnet.get_next_ip_for_allocation(
                    excl, count=pending
                )
                self.queue.fill(addresses)
                self._update_counter(-len(addresses))

    @classmethod
    def clean_cache(cls, subnet: Subnet):
        pass

    @classmethod
    def remove_cache(cls, subnet: Subnet):
        """Remove cache for this subnet"""
        with cls.pool_lock:
            cls.pool.pop(str(subnet), None)


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
                f"IP address type {alloc_type} is not allowed to use allocate_new."
            )

        if user is None:
            if alloc_type == IPADDRESS_TYPE.USER_RESERVED:
                raise AssertionError(
                    "Must provide user for USER_RESERVED alloc_type."
                )
        else:
            if alloc_type != IPADDRESS_TYPE.USER_RESERVED:
                raise AssertionError(
                    "Must not provide user for alloc_type other "
                    "than USER_RESERVED."
                )

    def _attempt_allocation(
        self, requested_address, alloc_type, user=None, subnet=None
    ) -> StaticIPAddress:
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
        ipaddress = StaticIPAddress(alloc_type=alloc_type, subnet=subnet)
        try:
            # Try to save this address to the database. Do this in a nested
            # transaction so that we can continue using the outer transaction
            # even if this breaks.
            with transaction.atomic():
                ipaddress.set_ip_address(requested_address.format())
                ipaddress.save()
        except IntegrityError:
            # The address is already taken.
            raise StaticIPAddressUnavailable(
                f"The IP address {requested_address.format()} is already in use."
            )
        else:
            # We deliberately do *not* save the user until now because it
            # might result in an IntegrityError, and we rely on the latter
            # in the code above to indicate an already allocated IP
            # address and nothing else.
            ipaddress.user = user
            ipaddress.save()
            return ipaddress

    def _attempt_allocation_of_free_address(
        self, requested_address, alloc_type, user=None, subnet=None
    ) -> StaticIPAddress:
        """Attempt to allocate `requested_address`, which is known to be free.

        It is known to be free *in this transaction*, so this could still
        fail. If it does fail because of a `UNIQUE_VIOLATION` it will request
        a retry, except while holding an addition lock. This is not perfect:
        other threads could jump in before acquiring the lock and steal an
        apparently free address. However, in stampede situations this appears
        to be effective enough. Experiment by increasing the `count` parameter
        in `test_allocate_new_works_under_extreme_concurrency`.

        This method shares a lot in common with `_attempt_allocation` so check
        out its documentation for more details.

        :param requested_address: The address to be allocated.
        :typr requested_address: IPAddress
        :param alloc_type: Allocation type.
        :param user: Optional user.
        :return: `StaticIPAddress` if successful.
        :raise RetryTransaction: if the address was already taken.
        """
        ipaddress = StaticIPAddress(alloc_type=alloc_type, subnet=subnet)
        try:
            # Try to save this address to the database. Do this in a nested
            # transaction so that we can continue using the outer transaction
            # even if this breaks.
            with orm.savepoint():
                ipaddress.set_ip_address(requested_address.format())
                ipaddress.save()
        except IntegrityError as error:
            if orm.is_unique_violation(error):
                # The address is taken. We could allow the transaction retry
                # machinery to take care of this, but instead we'll ask it to
                # retry with the `address_allocation` lock. We can't take it
                # here because we're already in a transaction; we need to exit
                # the transaction, take the lock, and only then try again.
                orm.request_transaction_retry(locks.address_allocation)
            else:
                raise
        else:
            # We deliberately do *not* save the user until now because it
            # might result in an IntegrityError, and we rely on the latter
            # in the code above to indicate an already allocated IP
            # address and nothing else.
            ipaddress.user = user
            ipaddress.save()
            return ipaddress

    def allocate_new(
        self,
        subnet=None,
        alloc_type=IPADDRESS_TYPE.AUTO,
        user=None,
        requested_address=None,
        exclude_addresses=None,
    ) -> StaticIPAddress:
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
        """
        # This check for `alloc_type` is important for later on. We rely on
        # detecting IntegrityError as a sign than an IP address is already
        # taken, and so we must first eliminate all other possible causes.
        self._verify_alloc_type(alloc_type, user)

        if subnet is None:
            if requested_address:
                subnet = Subnet.objects.get_best_subnet_for_ip(
                    requested_address
                )
            else:
                raise StaticIPAddressOutOfRange(
                    "Could not find an appropriate subnet."
                )

        if requested_address is None:
            with FreeIPAddress(subnet, exclude_addresses) as free_address:
                ip = self._attempt_allocation_of_free_address(
                    free_address,
                    alloc_type,
                    user=user,
                    subnet=subnet,
                )
            return ip
        else:
            requested_address = IPAddress(requested_address)
            from maasserver.models import StaticIPAddress

            if (
                StaticIPAddress.objects.filter(ip=str(requested_address))
                .exclude(alloc_type=IPADDRESS_TYPE.DISCOVERED)
                .exists()
            ):
                raise StaticIPAddressUnavailable(
                    f"The IP address {requested_address} is already in use."
                )

            subnet.validate_static_ip(requested_address)
            return self._attempt_allocation(
                requested_address, alloc_type, user=user, subnet=subnet
            )

    def _get_special_mappings(self, domain, raw_ttl=False):
        """Get the special mappings, possibly limited to a single Domain.

        This function is responsible for creating these mappings:
        - any USER_RESERVED IP that has no name (dnsrr or node),
        - any IP not associated with a Node,
        - any IP associated with a DNSResource.

        Addresses that are associated with both a Node and a DNSResource behave
        thusly:
        - Both forward mappings include the address
        - The reverse mapping points only to the Node (and is the
          responsibility of the caller.)

        The caller is responsible for addresses otherwise derived from nodes.

        Because of how the get hostname_ip_mapping code works, we actually need
        to fetch ALL of the entries for subnets, but forward mappings are
        domain-specific.

        :param domain: limit return to just the given Domain.  If anything
            other than a Domain is passed in (e.g., a Subnet or None), we
            return all of the reverse mappings.
        :param raw_ttl: Boolean, if True then just return the address_ttl,
            otherwise, coalesce the address_ttl to be the correct answer for
            zone generation.
        :return: a (default) dict of hostname: HostnameIPMapping entries.
        """
        default_ttl = "%d" % Config.objects.get_config("default_dns_ttl")
        # raw_ttl says that we don't coalesce, but we need to pick one, so we
        # go with DNSResource if it is involved.
        if raw_ttl:
            ttl_clause = """COALESCE(dnsrr.address_ttl, node.address_ttl)"""
        else:
            ttl_clause = (
                """
                COALESCE(
                    dnsrr.address_ttl,
                    dnsrr.ttl,
                    node.address_ttl,
                    node.ttl,
                    %s)"""
                % default_ttl
            )
        # And here is the SQL query of doom.  Build up inner selects to get the
        # view of a DNSResource (and Node) that we need, and finally use
        # domain2 to handle the case where an FQDN is also the name of a domain
        # that we know.
        sql_query = (
            """
            SELECT
                COALESCE(dnsrr.fqdn, node.fqdn) AS fqdn,
                node.system_id,
                node.node_type,
                staticip.user_id,
                """
            + ttl_clause
            + """ AS ttl,
                staticip.ip,
                dnsrr.id AS dnsresource_id
            FROM
                maasserver_staticipaddress AS staticip
            LEFT JOIN (
                /* Create a dnsrr that has what we need. */
                SELECT
                    CASE WHEN dnsrr.name = '@' THEN
                        dom.name
                    ELSE
                        CONCAT(dnsrr.name, '.', dom.name)
                    END AS fqdn,
                    dom.name as dom_name,
                    dnsrr.domain_id,
                    dnsrr.address_ttl,
                    dom.ttl,
                    dia.staticipaddress_id AS dnsrr_sip_id,
                    dom2.id AS dom2_id,
                    dnsrr.id AS id
                FROM maasserver_dnsresource_ip_addresses AS dia
                JOIN maasserver_dnsresource AS dnsrr ON
                    dia.dnsresource_id = dnsrr.id
                JOIN maasserver_domain AS dom ON
                    dnsrr.domain_id = dom.id
                LEFT JOIN maasserver_domain AS dom2 ON
                    CONCAT(dnsrr.name, '.', dom.name) = dom2.name OR (
                        dnsrr.name = '@' AND
                        dom.name SIMILAR TO CONCAT('[-A-Za-z0-9]*.', dom2.name)
                    )
                ) AS dnsrr ON
                    dnsrr_sip_id = staticip.id
            LEFT JOIN (
                /* Create a node that has what we need. */
                SELECT
                    CONCAT(nd.hostname, '.', dom.name) AS fqdn,
                    dom.name as dom_name,
                    nd.system_id,
                    nd.node_type,
                    nd.owner_id AS user_id,
                    nd.domain_id,
                    nd.address_ttl,
                    dom.ttl,
                    iia.staticipaddress_id AS node_sip_id,
                    dom2.id AS dom2_id
                FROM maasserver_interface_ip_addresses AS iia
                JOIN maasserver_interface AS iface ON
                    iia.interface_id = iface.id
                JOIN maasserver_nodeconfig AS nodeconfig ON
                    nodeconfig.id = iface.node_config_id
                JOIN maasserver_node AS nd ON
                    nd.current_config_id = nodeconfig.id
                JOIN maasserver_domain AS dom ON
                    nd.domain_id = dom.id
                LEFT JOIN maasserver_domain AS dom2 ON
                    CONCAT(nd.hostname, '.', dom.name) = dom2.name
                ) AS node ON
                    node_sip_id = staticip.id
            WHERE
                (staticip.ip IS NOT NULL AND
                 host(staticip.ip) != '' AND
                 staticip.temp_expires_on IS NULL) AND
                """
        )

        query_parms = []
        if isinstance(domain, Domain):
            if domain.is_default():
                # The default domain is extra special, since it needs to have
                # A/AAAA RRs for any USER_RESERVED addresses that have no name
                # otherwise attached to them.
                # We need to get all of the entries that are:
                # - in this domain and have a dnsrr associated, OR
                # - are USER_RESERVED and have NO fqdn associated at all.
                sql_query += """ ((
                        staticip.alloc_type = %s AND
                        dnsrr.fqdn IS NULL AND
                        node.fqdn IS NULL
                    ) OR (
                        dnsrr.fqdn IS NOT NULL AND
                        (
                            dnsrr.dom2_id = %s OR
                            node.dom2_id = %s OR
                            dnsrr.domain_id = %s OR
                            node.domain_id = %s)))"""
                query_parms += [IPADDRESS_TYPE.USER_RESERVED]
            else:
                # For domains, we only need answers for the domain we were
                # given.  These can can possibly come from either the child or
                # the parent for glue.  Anything with a node associated will be
                # found inside of get_hostname_ip_mapping() - we need any
                # entries that are:
                # - in this domain and have a dnsrr associated.
                sql_query += """ (
                    dnsrr.fqdn IS NOT NULL AND
                    (
                        dnsrr.dom2_id = %s OR
                        node.dom2_id = %s OR
                        dnsrr.domain_id = %s OR
                        node.domain_id = %s))"""
            query_parms += [domain.id, domain.id, domain.id, domain.id]
        else:
            # In the subnet map, addresses attached to nodes only map back to
            # the node, since some things don't like multiple PTR RRs in
            # answers from the DNS.
            # Since that is handled in get_hostname_ip_mapping, we exclude
            # anything where the node also has a link to the address.
            domain = None
            sql_query += """ ((
                    node.fqdn IS NULL AND dnsrr.fqdn IS NOT NULL
                ) OR (
                    staticip.alloc_type = %s AND
                    dnsrr.fqdn IS NULL AND
                    node.fqdn IS NULL))"""
            query_parms += [IPADDRESS_TYPE.USER_RESERVED]

        default_domain = Domain.objects.get_default_domain()
        mapping = defaultdict(HostnameIPMapping)
        cursor = connection.cursor()
        cursor.execute(sql_query, query_parms)
        for result in cursor.fetchall():
            result = SpecialMappingQueryResult(*result)
            if result.fqdn is None or result.fqdn == "":
                fqdn = "{}.{}".format(
                    get_ip_based_hostname(result.ip),
                    default_domain.name,
                )
            else:
                fqdn = result.fqdn
            # It is possible that there are both Node and DNSResource entries
            # for this fqdn.  If we have any system_id, preserve it.  Ditto for
            # TTL.  It is left as an exercise for the admin to make sure that
            # the any non-default TTL applied to the Node and DNSResource are
            # equal.
            entry = mapping[fqdn]
            if result.system_id is not None:
                entry.node_type = result.node_type
                entry.system_id = result.system_id
            if result.ttl is not None:
                entry.ttl = result.ttl
            if result.user_id is not None:
                entry.user_id = result.user_id
            entry.ips.add(result.ip)
            entry.dnsresource_id = result.dnsresource_id
        return mapping

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
        default_ttl = "%d" % Config.objects.get_config("default_dns_ttl")
        if raw_ttl:
            ttl_clause = """node.address_ttl"""
        else:
            ttl_clause = (
                """
                COALESCE(
                    node.address_ttl,
                    domain.ttl,
                    %s)"""
                % default_ttl
            )
        sql_query = (
            """
            SELECT DISTINCT ON (fqdn, is_boot, family)
                CONCAT(node.hostname, '.', domain.name) AS fqdn,
                node.system_id,
                node.node_type,
                staticip.user_id,
                """
            + ttl_clause
            + """ AS ttl,
                staticip.ip,
                COALESCE(
                    node.boot_interface_id IS NOT NULL AND
                    (
                        node.boot_interface_id = interface.id OR
                        node.boot_interface_id = parent.id OR
                        node.boot_interface_id = parent_parent.id
                    ),
                    False
                ) AS is_boot,
                CASE
                    WHEN interface.type = 'bridge' AND
                        parent_parent.id = node.boot_interface_id THEN 1
                    WHEN interface.type = 'bridge' AND
                        parent.id = node.boot_interface_id THEN 2
                    WHEN interface.type = 'bond' AND
                        parent.id = node.boot_interface_id THEN 3
                    WHEN interface.type = 'physical' AND
                        interface.id = node.boot_interface_id THEN 4
                    WHEN interface.type = 'bond' THEN 5
                    WHEN interface.type = 'physical' THEN 6
                    WHEN interface.type = 'vlan' THEN 7
                    WHEN interface.type = 'alias' THEN 8
                    WHEN interface.type = 'unknown' THEN 9
                    ELSE 10
                END AS preference,
                family(staticip.ip) AS family
            FROM
                maasserver_interface AS interface
            LEFT OUTER JOIN maasserver_interfacerelationship AS rel ON
                interface.id = rel.child_id
            LEFT OUTER JOIN maasserver_interface AS parent ON
                rel.parent_id = parent.id
            LEFT OUTER JOIN maasserver_interfacerelationship AS parent_rel ON
                parent.id = parent_rel.child_id
            LEFT OUTER JOIN maasserver_interface AS parent_parent ON
                parent_rel.parent_id = parent_parent.id
            JOIN maasserver_nodeconfig as nodeconfig ON
                nodeconfig.id = interface.node_config_id
            JOIN maasserver_node AS node ON
                node.current_config_id = nodeconfig.id
            JOIN maasserver_domain AS domain ON
                domain.id = node.domain_id
            JOIN maasserver_interface_ip_addresses AS link ON
                link.interface_id = interface.id
            JOIN maasserver_staticipaddress AS staticip ON
                staticip.id = link.staticipaddress_id
            """
        )
        if isinstance(domain_or_subnet, Domain):
            # The model has nodes in the parent domain, but they actually live
            # in the child domain.  And the parent needs the glue.  So we
            # return such nodes addresses in _BOTH_ the parent and the child
            # domains. domain2.name will be non-null if this host's fqdn is the
            # name of a domain in MAAS.
            sql_query += """
            LEFT JOIN maasserver_domain AS domain2 ON
                /* Pick up another copy of domain looking for instances of
                 * nodes a the top of a domain.
                 */ domain2.name = CONCAT(node.hostname, '.', domain.name)
            WHERE
                (domain2.id = %s OR node.domain_id = %s) AND
            """
            query_parms = [domain_or_subnet.id, domain_or_subnet.id]
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
                staticip.temp_expires_on IS NULL
            ORDER BY
                fqdn,
                is_boot DESC,
                family,
                preference,
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
                interface.id,
                inet 'fc00::/7' >> ip /* ULA after non-ULA */
            """
        iface_sql_query = (
            """
            SELECT
                CONCAT(node.hostname, '.', domain.name) AS fqdn,
                node.system_id,
                node.node_type,
                node.owner_id AS user_id,
                """
            + ttl_clause
            + """ AS ttl,
                staticip.ip,
                interface.name,
                alloc_type != 6 /* DISCOVERED */ AS assigned
            FROM
                maasserver_interface AS interface
            JOIN maasserver_nodeconfig AS nodeconfig ON
                nodeconfig.id = interface.node_config_id
            JOIN maasserver_node AS node ON
                node.current_config_id = nodeconfig.id
            JOIN maasserver_domain AS domain ON
                domain.id = node.domain_id
            JOIN maasserver_interface_ip_addresses AS link ON
                link.interface_id = interface.id
            JOIN maasserver_staticipaddress AS staticip ON
                staticip.id = link.staticipaddress_id
            """
        )
        if isinstance(domain_or_subnet, Domain):
            # This logic is similar to the logic in sql_query above.
            iface_sql_query += """
            LEFT JOIN maasserver_domain AS domain2 ON
                /* Pick up another copy of domain looking for instances of
                 * the name as the top of a domain.
                 */
                domain2.name = CONCAT(
                    interface.name, '.', node.hostname, '.', domain.name)
            WHERE
                (domain2.id = %s OR node.domain_id = %s) AND
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
                staticip.temp_expires_on IS NULL
            ORDER BY
                node.hostname,
                assigned DESC, /* Return all assigned IPs for a node first. */
                interface.id
            """
        # We get user reserved et al mappings first, so that we can overwrite
        # TTL as we process the return from the SQL horror above.
        mapping = self._get_special_mappings(domain_or_subnet, raw_ttl)
        # All of the mappings that we got mean that we will only want to add
        # addresses for the boot interface (is_boot == True).
        iface_is_boot = defaultdict(
            bool, {hostname: True for hostname in mapping.keys()}
        )
        assigned_ips = defaultdict(bool)
        cursor.execute(sql_query, query_parms)
        # The records from the query provide, for each hostname (after
        # stripping domain), the boot and non-boot interface ip address in ipv4
        # and ipv6.  Our task: if there are boot interace IPs, they win.  If
        # there are none, then whatever we got wins.  The ORDER BY means that
        # we will see all of the boot interfaces before we see any non-boot
        # interface IPs.  See Bug#1584850
        for result in cursor.fetchall():
            result = MappingQueryResult(*result)
            entry = mapping[result.fqdn]
            entry.node_type = result.node_type
            entry.system_id = result.system_id
            if result.user_id is not None:
                entry.user_id = result.user_id
            entry.ttl = result.ttl
            if result.is_boot:
                iface_is_boot[result.fqdn] = True
            # If we have an IP on the right interface type, save it.
            if result.is_boot == iface_is_boot[result.fqdn]:
                entry.ips.add(result.ip)
        # Next, get all the addresses, on all the interfaces, and add the ones
        # that are not already present on the FQDN as $IFACE.$FQDN.  Exclude
        # any discovered addresses once there are any non-discovered addresses.
        cursor.execute(iface_sql_query, query_parms)
        for result in cursor.fetchall():
            result = InterfaceMappingResult(*result)
            if result.assigned:
                assigned_ips[result.fqdn] = True
            # If this is an assigned IP, or there are NO assigned IPs on the
            # node, then consider adding the IP.
            if result.assigned or not assigned_ips[result.fqdn]:
                if result.ip not in mapping[result.fqdn].ips:
                    fqdn = "{}.{}".format(
                        get_iface_name_based_hostname(result.iface_name),
                        result.fqdn,
                    )
                    entry = mapping[fqdn]
                    entry.node_type = result.node_type
                    entry.system_id = result.system_id
                    if result.user_id is not None:
                        entry.user_id = result.user_id
                    entry.ttl = result.ttl
                    entry.ips.add(result.ip)
        return mapping

    def filter_by_ip_family(self, family):
        possible_families = map_enum_reverse(IPADDRESS_FAMILY)
        if family not in possible_families:
            raise ValueError(
                f"IP address family {family} is not a member of IPADDRESS_FAMILY."
            )
        return self.annotate(
            ip_family=Func(F("ip"), function="family")
        ).filter(ip_family=Value(family))


class StaticIPAddress(CleanSave, TimestampedModel):
    class Meta:
        verbose_name = "Static IP Address"
        verbose_name_plural = "Static IP Addresses"
        unique_together = ("alloc_type", "ip")
        constraints = [
            UniqueConstraint(
                fields=["ip"],
                condition=~Q(alloc_type=IPADDRESS_TYPE.DISCOVERED),
                name="maasserver_staticipaddress_discovered_uniq",
            )
        ]

    # IP can be none when a DHCP lease has expired: in this case the entry
    # in the StaticIPAddress only materializes the connection between an
    # interface and asubnet.
    ip = GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP",
    )

    alloc_type = IntegerField(
        editable=False, null=False, blank=False, default=IPADDRESS_TYPE.AUTO
    )

    # Subnet is only null for IP addresses allocate before the new networking
    # model.
    subnet = ForeignKey(
        "Subnet", editable=True, blank=True, null=True, on_delete=CASCADE
    )

    user = ForeignKey(
        User,
        default=None,
        blank=True,
        null=True,
        editable=False,
        on_delete=PROTECT,
    )

    # Used only by DISCOVERED address to set the lease_time for an active
    # lease. Time is in seconds.
    lease_time = IntegerField(
        default=0, editable=False, null=False, blank=False
    )

    # Used to mark a `StaticIPAddress` as temperary until the assignment
    # can be confirmed to be free in the subnet.
    temp_expires_on = DateTimeField(
        null=True, blank=True, editable=False, db_index=True
    )

    objects = StaticIPAddressManager()

    def __str__(self):
        # Attempt to show the symbolic alloc_type name if possible.
        type_names = map_enum_reverse(IPADDRESS_TYPE)
        strtype = type_names.get(self.alloc_type, "%s" % self.alloc_type)
        return f"{self.ip}:type={strtype}"

    @property
    def alloc_type_name(self):
        """Returns a human-readable representation of the `alloc_type`."""
        return IPADDRESS_TYPE_CHOICES_DICT.get(self.alloc_type, "")

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
        return self.interface_set.first()

    def get_interface_link_type(self):
        """Return the `INTERFACE_LINK_TYPE`."""
        if self.alloc_type == IPADDRESS_TYPE.AUTO:
            return INTERFACE_LINK_TYPE.AUTO
        elif self.alloc_type in (
            IPADDRESS_TYPE.DHCP,
            IPADDRESS_TYPE.DISCOVERED,
        ):
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
            interface.type for interface in self.interface_set.all()
        ]
        return interface_types == [INTERFACE_TYPE.UNKNOWN]

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
            discovered_ip = self._get_related_discovered_ip()
            if discovered_ip is not None:
                return discovered_ip.ip, discovered_ip.subnet
        return self.ip, self.subnet

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
                    {"ip": ["IP address must be specified."]}
                )
        if self.alloc_type == IPADDRESS_TYPE.DHCP:
            if self.ip:
                raise ValidationError(
                    {"ip": ["IP address must not be specified."]}
                )

        if self.ip and self.subnet and self.subnet.cidr:
            address = self.get_ipaddress()
            network = self.subnet.get_ipnetwork()
            if address not in network:
                raise ValidationError(
                    {
                        "ip": [
                            f"IP address {address} is not within the subnet: {network}."
                        ]
                    }
                )

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
        return {
            interface.mac_address for interface in self.interface_set.all()
        }

    def clean(self, *args, **kwargs):
        super().clean(*args, **kwargs)
        self.clean_subnet_and_ip_consistent()

    def _set_subnet(self, subnet, interfaces=None):
        """Resets the Subnet for this StaticIPAddress, making sure to update
        the VLAN for a related Interface (if the VLAN has changed).
        """
        self.subnet = subnet
        if interfaces is not None:
            for iface in interfaces:
                if (
                    iface is not None
                    and subnet is not None
                    and iface.vlan_id != subnet.vlan_id
                ):
                    iface.vlan = subnet.vlan
                    iface.save()

    def render_json(self, with_username=False, with_summary=False):
        """Render a representation of this `StaticIPAddress` object suitable
        for converting to JSON. Includes optional parameters wherever a join
        would be implied by including a specific piece of information."""
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
        if with_summary:
            iface = self.get_interface()
            node = self.get_node()
            if node is not None:
                data["node_summary"] = {
                    "system_id": node.system_id,
                    "node_type": node.node_type,
                    "fqdn": node.fqdn,
                    "hostname": node.hostname,
                    "is_container": node.parent_id is not None,
                }
                if iface is not None:
                    data["node_summary"]["via"] = iface.name
                if (
                    with_username
                    and self.alloc_type != IPADDRESS_TYPE.DISCOVERED
                ):
                    # If a user owns this node, overwrite any username we found
                    # earlier. A node's owner takes precedence.
                    if node.owner and node.owner.username:
                        data["user"] = node.owner.username
            # This IP address is used as DNS resource.
            dns_records = [
                {
                    "id": resource.id,
                    "name": resource.name,
                    "domain": resource.domain.name,
                }
                for resource in self.dnsresource_set.all()
            ]
            if dns_records:
                data["dns_records"] = dns_records
            # This IP address is used as a BMC.
            bmcs = [
                {
                    "id": bmc.id,
                    "power_type": bmc.power_type,
                    "nodes": [
                        {
                            "system_id": node.system_id,
                            "hostname": node.hostname,
                        }
                        for node in bmc.node_set.all()
                    ],
                }
                for bmc in self.bmc_set.all()
            ]
            if bmcs:
                data["bmcs"] = bmcs
        return data

    def set_ip_address(self, ipaddr):
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

    def _get_related_discovered_ip(self):
        """Return the related DISCOVERED IP address for this IP address.

        This comes from looking at the DISCOVERED IP addresses assigned to the
        related interfaces.
        """
        return (
            StaticIPAddress.objects.filter(
                interface__in=self.interface_set.all(),
                alloc_type=IPADDRESS_TYPE.DISCOVERED,
                ip__isnull=False,
            )
            .order_by("-id")
            .first()
        )
