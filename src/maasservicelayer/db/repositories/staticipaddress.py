#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from collections import defaultdict
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv6Address
from typing import List, Optional, Type

from pydantic import IPvAnyAddress
from sqlalchemy import and_, func, select, Table, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.operators import eq

from maascommon.dns import (
    get_iface_name_based_hostname,
    get_ip_based_hostname,
    HostnameIPMapping,
)
from maascommon.enums.ipaddress import IpAddressFamily, IpAddressType
from maascommon.enums.node import NodeTypeEnum
from maasservicelayer.builders.staticipaddress import StaticIPAddressBuilder
from maasservicelayer.db.filters import Clause, ClauseFactory, QuerySpec
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import (
    InterfaceIPAddressTable,
    InterfaceTable,
    NodeConfigTable,
    NodeTable,
    StaticIPAddressTable,
    SubnetTable,
)
from maasservicelayer.models.domains import Domain
from maasservicelayer.models.fields import MacAddress
from maasservicelayer.models.interfaces import Interface
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.utils.date import utcnow


class StaticIPAddressClauseFactory(ClauseFactory):
    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(StaticIPAddressTable.c.id, id))

    @classmethod
    def with_node_type(cls, type: NodeTypeEnum) -> Clause:
        return Clause(condition=eq(NodeTable.c.node_type, type))

    @classmethod
    def with_node_system_id(cls, system_id: str) -> Clause:
        return Clause(condition=eq(NodeTable.c.system_id, system_id))

    @classmethod
    def with_subnet_id(cls, subnet_id: int) -> Clause:
        return Clause(
            condition=eq(StaticIPAddressTable.c.subnet_id, subnet_id)
        )

    @classmethod
    def with_subnet_id_in(cls, subnet_ids: list[int]) -> Clause:
        return Clause(
            condition=StaticIPAddressTable.c.subnet_id.in_(subnet_ids)
        )

    @classmethod
    def with_ip(cls, ip: IPvAnyAddress) -> Clause:
        return Clause(condition=eq(StaticIPAddressTable.c.ip, ip))

    @classmethod
    def with_user_id(cls, user_id: int) -> Clause:
        return Clause(condition=eq(StaticIPAddressTable.c.user_id, user_id))


@dataclass
class MappingBaseResult:
    fqdn: str | None
    system_id: str | None
    node_type: NodeTypeEnum | None
    user_id: int | None
    ttl: int | None
    ip: IPv4Address | IPv6Address | None
    node_id: int | None


@dataclass
class SpecialMappingQueryResult(MappingBaseResult):
    dnsresource_id: int | None


@dataclass
class MappingQueryResult(MappingBaseResult):
    is_boot: bool
    preference: int
    family: int


@dataclass
class InterfaceMappingResult(MappingBaseResult):
    iface_name: str
    assigned: bool


class StaticIPAddressRepository(BaseRepository):
    def get_repository_table(self) -> Table:
        return StaticIPAddressTable

    def get_model_factory(self) -> Type[StaticIPAddress]:
        return StaticIPAddress

    async def create_or_update(
        self, builder: StaticIPAddressBuilder
    ) -> StaticIPAddress:
        now = utcnow()
        builder.created = now
        builder.updated = now
        resource = self.mapper.build_resource(builder)
        stmt = insert(StaticIPAddressTable).values(**resource.get_values())
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=[
                StaticIPAddressTable.c.ip,
                StaticIPAddressTable.c.alloc_type,
            ],
            set_=resource.get_values(),
        ).returning(StaticIPAddressTable)

        result = (await self.execute_stmt(upsert_stmt)).one()
        return StaticIPAddress(**result._asdict())

    async def get_discovered_ips_in_family_for_interfaces(
        self,
        interfaces: List[Interface],
        family: IpAddressFamily = IpAddressFamily.IPV4,
    ) -> List[StaticIPAddress]:
        stmt = (
            select(StaticIPAddressTable)
            .select_from(StaticIPAddressTable)
            .join(
                InterfaceIPAddressTable,
                InterfaceIPAddressTable.c.staticipaddress_id
                == StaticIPAddressTable.c.id,
            )
            .join(
                InterfaceTable,
                InterfaceTable.c.id == InterfaceIPAddressTable.c.interface_id,
            )
            .where(
                and_(
                    eq(
                        func.family(StaticIPAddressTable.c.ip),
                        IpAddressFamily.IPV4.value,
                    ),
                    InterfaceTable.c.id.in_(
                        [interface.id for interface in interfaces]
                    ),
                ),
            )
        )

        result = (
            await self.execute_stmt(
                stmt,
            )
        ).all()

        return [StaticIPAddress(**row._asdict()) for row in result]

    async def get_for_interfaces(
        self,
        interfaces: List[Interface],
        subnet: Optional[Subnet] = None,
        ip: Optional[StaticIPAddress] = None,
        alloc_type: Optional[IpAddressType] = None,
    ) -> StaticIPAddress | None:
        stmt = (
            select(StaticIPAddressTable)
            .select_from(InterfaceTable)
            .join(
                InterfaceIPAddressTable,
                InterfaceIPAddressTable.c.interface_id == InterfaceTable.c.id,
            )
            .join(
                StaticIPAddressTable,
                StaticIPAddressTable.c.id
                == InterfaceIPAddressTable.c.staticipaddress_id,
            )
            .filter(
                InterfaceTable.c.id.in_([iface.id for iface in interfaces]),
            )
        )

        if subnet:
            stmt = stmt.filter(StaticIPAddressTable.c.subnet_id == subnet.id)

        if ip:
            stmt = stmt.filter(StaticIPAddressTable.c.ip == ip.ip)

        if alloc_type:
            stmt = stmt.filter(
                StaticIPAddressTable.c.alloc_type == alloc_type.value
            )

        result = (await self.execute_stmt(stmt)).first()

        if result:
            return StaticIPAddress(**result._asdict())
        return None

    async def get_for_nodes(self, query: QuerySpec) -> list[StaticIPAddress]:
        stmt = (
            select(
                StaticIPAddressTable,
            )
            .select_from(NodeTable)
            .join(
                NodeConfigTable,
                NodeTable.c.current_config_id == NodeConfigTable.c.id,
            )
            .join(
                InterfaceTable,
                NodeConfigTable.c.id == InterfaceTable.c.node_config_id,
            )
            .join(
                InterfaceIPAddressTable,
                InterfaceTable.c.id == InterfaceIPAddressTable.c.interface_id,
            )
            .join(
                StaticIPAddressTable,
                InterfaceIPAddressTable.c.staticipaddress_id
                == StaticIPAddressTable.c.id,
            )
            .join(
                SubnetTable,
                SubnetTable.c.id == StaticIPAddressTable.c.subnet_id,
            )
            .where(query.where.condition)
        )
        results = (await self.execute_stmt(stmt)).all()
        return [StaticIPAddress(**row._asdict()) for row in results]

    async def get_mac_addresses(self, query: QuerySpec) -> list[MacAddress]:
        stmt = (
            select(InterfaceTable.c.mac_address)
            .select_from(InterfaceTable)
            .join(
                InterfaceIPAddressTable,
                InterfaceIPAddressTable.c.interface_id == InterfaceTable.c.id,
            )
            .join(
                StaticIPAddressTable,
                StaticIPAddressTable.c.id
                == InterfaceIPAddressTable.c.staticipaddress_id,
            )
        )
        stmt = query.enrich_stmt(stmt)
        results = (await self.execute_stmt(stmt)).all()
        return [MacAddress(row._asdict()["mac_address"]) for row in results]

    async def _get_special_mappings(
        self,
        default_domain: Domain,
        default_ttl: int,
        domain_id: int | None = None,
        raw_ttl: bool = False,
    ) -> dict[str, HostnameIPMapping]:
        """Get the special mappings, possibly limited to a single Domain.

        NOTE: This has been moved from src/maasserver/models/staticipaddress.py
        and the relevant test has been moved to the servicelayer tests.

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

        Params:
            - default_domain: MAAS default domain
            - default_ttl: MAAS default TTL
            - domain_id: limit return to just the given Domain.
            - raw_ttl: if True then just return the address_ttl, otherwise,
            coalesce the address_ttl to be the correct answer for zone generation.
        Returns:
            a (default) dict of hostname: HostnameIPMapping entries.
        """
        # raw_ttl says that we don't coalesce, but we need to pick one, so we
        # go with DNSResource if it is involved.
        if raw_ttl:
            ttl_clause = """COALESCE(dnsrr.address_ttl, node.address_ttl)"""
        else:
            ttl_clause = f"""
                COALESCE(
                    dnsrr.address_ttl,
                    dnsrr.ttl,
                    node.address_ttl,
                    node.ttl,
                    {default_ttl}
                )"""
        # And here is the SQL query of doom.  Build up inner selects to get the
        # view of a DNSResource (and Node) that we need, and finally use
        # domain2 to handle the case where an FQDN is also the name of a domain
        # that we know.
        sql_query = (
            """
            SELECT
                COALESCE(dnsrr.fqdn, node.fqdn) AS fqdn,
                node.system_id AS system_id,
                node.node_type AS node_type,
                node.id AS node_id, /* added in 2025 */
                staticip.user_id AS user_id,
                """
            + ttl_clause
            + """ AS ttl,
                staticip.ip AS ip,
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
                    nd.id, /* added in 2025 */
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

        if domain_id is not None:
            if domain_id == default_domain.id:
                # The default domain is extra special, since it needs to have
                # A/AAAA RRs for any USER_RESERVED addresses that have no name
                # otherwise attached to them.
                # We need to get all of the entries that are:
                # - in this domain and have a dnsrr associated, OR
                # - are USER_RESERVED and have NO fqdn associated at all.
                sql_query += f""" ((
                        staticip.alloc_type = {IpAddressType.USER_RESERVED} AND
                        dnsrr.fqdn IS NULL AND
                        node.fqdn IS NULL
                    ) OR (
                        dnsrr.fqdn IS NOT NULL AND
                        (
                            dnsrr.dom2_id = {domain_id} OR
                            node.dom2_id = {domain_id} OR
                            dnsrr.domain_id = {domain_id} OR
                            node.domain_id = {domain_id})))"""
            else:
                # For domains, we only need answers for the domain we were
                # given.  These can can possibly come from either the child or
                # the parent for glue.  Anything with a node associated will be
                # found inside of get_hostname_ip_mapping() - we need any
                # entries that are:
                # - in this domain and have a dnsrr associated.
                sql_query += f""" (
                    dnsrr.fqdn IS NOT NULL AND
                    (
                        dnsrr.dom2_id = {domain_id} OR
                        node.dom2_id = {domain_id} OR
                        dnsrr.domain_id = {domain_id} OR
                        node.domain_id = {domain_id}))"""
        else:
            # In the subnet map, addresses attached to nodes only map back to
            # the node, since some things don't like multiple PTR RRs in
            # answers from the DNS.
            # Since that is handled in get_hostname_ip_mapping, we exclude
            # anything where the node also has a link to the address.
            sql_query += f""" ((
                    node.fqdn IS NULL AND dnsrr.fqdn IS NOT NULL
                ) OR (
                    staticip.alloc_type = {IpAddressType.USER_RESERVED} AND
                    dnsrr.fqdn IS NULL AND
                    node.fqdn IS NULL))"""
        sql_query = text(sql_query)
        results = (await self.execute_stmt(sql_query)).all()
        mapping = defaultdict(HostnameIPMapping)
        for result in results:
            result = SpecialMappingQueryResult(**result._asdict())
            if result.fqdn is None or result.fqdn == "":
                fqdn = (
                    f"{get_ip_based_hostname(result.ip)}.{default_domain.name}"
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

    async def get_hostname_ip_mapping(
        self,
        default_domain: Domain,
        default_ttl: int,
        domain_id: int | None = None,
        raw_ttl: bool = False,
    ) -> dict[str, HostnameIPMapping]:
        """Return hostname mappings for `StaticIPAddress` entries.

        NOTE: This has been moved from src/maasserver/models/staticipaddress.py
        and the relevant tests are still in src/maasserver/models/tests/test_staticipaddress.py

        Returns a mapping `{hostnames -> (ttl, [ips])}` corresponding to
        current `StaticIPAddress` objects for the nodes in `domain`, or
        `subnet`.

        At most one IPv4 address and one IPv6 address will be returned per
        node, each the one for whichever `Interface` was created first.

        The returned name is an FQDN (no trailing dot.)

        Params:
            - default_domain: MAAS default domain.
            - default_ttl: MAAS default TTL.
            - domain_id: limit return to just the given Domain.
            - raw_ttl: if True then just return the address_ttl, otherwise,
            coalesce the address_ttl to be the correct answer for zone generation.
        Returns:
            a (default) dict of hostname: HostnameIPMapping entries.
        """

        # DISTINCT ON returns the first matching row for any given
        # hostname, using the query's ordering.  Here, we're trying to
        # return the IPs for the oldest Interface address.

        if raw_ttl:
            ttl_clause = """node.address_ttl"""
        else:
            ttl_clause = f"""
                COALESCE(
                    node.address_ttl,
                    domain.ttl,
                    {default_ttl}
                )"""
        sql_query = (
            """
            SELECT DISTINCT ON (fqdn, is_boot, family)
                CONCAT(node.hostname, '.', domain.name) AS fqdn,
                node.system_id AS system_id,
                node.node_type AS node_type,
                node.id AS node_id, /* added in 2025 */
                staticip.user_id AS user_id,
                """
            + ttl_clause
            + """ AS ttl,
                staticip.ip AS ip,
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
        if domain_id is not None:
            # The model has nodes in the parent domain, but they actually live
            # in the child domain.  And the parent needs the glue.  So we
            # return such nodes addresses in _BOTH_ the parent and the child
            # domains. domain2.name will be non-null if this host's fqdn is the
            # name of a domain in MAAS.
            sql_query += f"""
            LEFT JOIN maasserver_domain AS domain2 ON
                /* Pick up another copy of domain looking for instances of
                 * nodes a the top of a domain.
                 */ domain2.name = CONCAT(node.hostname, '.', domain.name)
            WHERE
                (domain2.id = {domain_id} OR node.domain_id = {domain_id}) AND
            """
        else:
            # For subnets, we need ALL the names, so that we can correctly
            # identify which ones should have the FQDN.  dns/zonegenerator.py
            # optimizes based on this, and only calls once with a subnet,
            # expecting to get all the subnets back in one table.
            sql_query += """
            WHERE
            """
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
                inet 'fc00::/7' >> ip /* ULA after non-ULA */,
                staticip.id
            """
        iface_sql_query = (
            """
            SELECT
                CONCAT(node.hostname, '.', domain.name) AS fqdn,
                node.system_id AS system_id,
                node.node_type AS node_type,
                node.owner_id AS user_id,
                node.id AS node_id, /* added in 2025 */
                """
            + ttl_clause
            + """ AS ttl,
                staticip.ip AS ip,
                interface.name AS iface_name,
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
        if domain_id is not None:
            # This logic is similar to the logic in sql_query above.
            iface_sql_query += f"""
            LEFT JOIN maasserver_domain AS domain2 ON
                /* Pick up another copy of domain looking for instances of
                 * the name as the top of a domain.
                 */
                domain2.name = CONCAT(
                    interface.name, '.', node.hostname, '.', domain.name)
            WHERE
                (domain2.id = {domain_id} OR node.domain_id = {domain_id}) AND
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
        mapping = await self._get_special_mappings(
            default_domain, default_ttl, domain_id, raw_ttl
        )
        # All of the mappings that we got mean that we will only want to add
        # addresses for the boot interface (is_boot == True).
        iface_is_boot = defaultdict(
            bool,
            {hostname: True for hostname in mapping.keys()},
        )
        assigned_ips = defaultdict(bool)
        sql_query = text(sql_query)
        results = (await self.execute_stmt(sql_query)).all()
        # The records from the query provide, for each hostname (after
        # stripping domain), the boot and non-boot interface ip address in ipv4
        # and ipv6.  Our task: if there are boot interace IPs, they win.  If
        # there are none, then whatever we got wins.  The ORDER BY means that
        # we will see all of the boot interfaces before we see any non-boot
        # interface IPs.  See Bug#1584850
        for result in results:
            result = MappingQueryResult(**result._asdict())
            assert result.fqdn is not None
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
        iface_sql_query = text(iface_sql_query)
        results = (await self.execute_stmt(iface_sql_query)).all()
        for result in results:
            result = InterfaceMappingResult(**result._asdict())
            assert result.fqdn is not None
            if result.assigned:
                assigned_ips[result.fqdn] = True
            # If this is an assigned IP, or there are NO assigned IPs on the
            # node, then consider adding the IP.
            if result.assigned or not assigned_ips[result.fqdn]:
                if result.ip not in mapping[result.fqdn].ips:
                    fqdn = f"{get_iface_name_based_hostname(result.iface_name)}.{result.fqdn}"
                    entry = mapping[fqdn]
                    entry.node_type = result.node_type
                    entry.system_id = result.system_id
                    if result.user_id is not None:
                        entry.user_id = result.user_id
                    entry.ttl = result.ttl
                    entry.ips.add(result.ip)
        return mapping
