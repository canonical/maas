#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from collections import defaultdict
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv6Address
from typing import Type

from sqlalchemy import and_, select, Table, text
from sqlalchemy.sql.operators import eq

from maascommon.dns import (
    get_iface_name_based_hostname,
    get_ip_based_hostname,
    HostnameIPMapping,
    HostnameRRsetMapping,
)
from maascommon.enums.ipaddress import IpAddressType
from maascommon.enums.node import NodeTypeEnum
from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import (
    DomainTable,
    ForwardDNSServerDomainsTable,
    ForwardDNSServerTable,
    GlobalDefaultTable,
)
from maasservicelayer.models.domains import Domain
from maasservicelayer.models.forwarddnsserver import ForwardDNSServer


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


@dataclass
class DnsDataMappingQueryResult:
    dnsresource_id: int | None = None
    name: str | None = None
    d_name: str | None = None
    system_id: str | None = None
    node_type: NodeTypeEnum | None = None
    user_id: int | None = None
    dnsdata_id: int | None = None
    ttl: int | None = None
    rrtype: int | None = None
    rrdata: str | None = None
    node_id: int | None = None


class DomainsClauseFactory(ClauseFactory):
    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(DomainTable.c.id, id))

    @classmethod
    def with_name(cls, name: str) -> Clause:
        return Clause(condition=eq(DomainTable.c.name, name))

    @classmethod
    def with_authoritative(cls, authoritative: bool) -> Clause:
        return Clause(condition=eq(DomainTable.c.authoritative, authoritative))

    @classmethod
    def with_ttl(cls, ttl: int) -> Clause:
        return Clause(condition=eq(DomainTable.c.ttl, ttl))


class DomainsRepository(BaseRepository[Domain]):
    def get_repository_table(self) -> Table:
        return DomainTable

    def get_model_factory(self) -> Type[Domain]:
        return Domain

    async def get_default_domain(self) -> Domain:
        stmt = (
            select(DomainTable)
            .select_from(GlobalDefaultTable)
            .join(
                DomainTable, DomainTable.c.id == GlobalDefaultTable.c.domain_id
            )
            .filter(GlobalDefaultTable.c.id == 0)
        )

        default_domain = (await self.execute_stmt(stmt)).one()

        return Domain(**default_domain._asdict())

    async def _get_special_mappings(
        self,
        default_ttl: int,
        domain_id: int | None = None,
        raw_ttl: bool = False,
        with_node_id: bool = False,
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

        default_domain = await self.get_default_domain()

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
                if with_node_id:
                    entry.node_id = result.node_id
            if result.ttl is not None:
                entry.ttl = result.ttl
            if result.user_id is not None:
                entry.user_id = result.user_id
            if result.ip is not None:
                entry.ips.add(result.ip)
            entry.dnsresource_id = result.dnsresource_id
        return mapping

    async def get_hostname_ip_mapping(
        self,
        default_ttl: int,
        domain_id: int | None = None,
        raw_ttl: bool = False,
        with_node_id: bool = False,
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
            default_ttl, domain_id, raw_ttl
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
            if with_node_id:
                entry.node_id = result.node_id
            if result.user_id is not None:
                entry.user_id = result.user_id
            entry.ttl = result.ttl
            if result.is_boot:
                iface_is_boot[result.fqdn] = True
            # If we have an IP on the right interface type, save it.
            if (
                result.is_boot == iface_is_boot[result.fqdn]
                and result.ip is not None
            ):
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
                    if with_node_id:
                        entry.node_id = result.node_id
                    if result.user_id is not None:
                        entry.user_id = result.user_id
                    entry.ttl = result.ttl
                    if result.ip is not None:
                        entry.ips.add(result.ip)
        return mapping

    async def get_hostname_dnsdata_mapping(
        self,
        domain_id: int,
        default_ttl: int,
        raw_ttl=False,
        with_ids=True,
        with_node_id=False,
    ) -> dict[str, HostnameRRsetMapping]:
        """Return hostname to RRset mapping for the specified domain.

        NOTE: This has been moved from src/maasserver/models/dnsdata.py and the
        relative tests are still in src/maasserver/models/tests/test_dnsdata.py
        """
        domain = await self.get_by_id(domain_id)
        if domain is None:
            self._raise_not_found_exception()
        if raw_ttl:
            ttl_clause = """dnsdata.ttl"""
        else:
            ttl_clause = f"""
                COALESCE(
                    dnsdata.ttl,
                    domain.ttl,
                    {default_ttl}
                )"""
        sql_query = f"""
            SELECT
                dnsresource.id AS dnsresource_id,
                dnsresource.name AS name,
                domain.name AS d_name,
                node.system_id AS system_id,
                node.node_type AS node_type,
                node.user_id AS user_id,
                dnsdata.id AS dnsdata_id,
                {ttl_clause} AS ttl,
                dnsdata.rrtype AS rrtype,
                dnsdata.rrdata AS rrdata,
                node.id AS node_id /* added in 2025 */
            FROM maasserver_dnsdata AS dnsdata
            JOIN maasserver_dnsresource AS dnsresource ON
                dnsdata.dnsresource_id = dnsresource.id
            JOIN maasserver_domain as domain ON
                dnsresource.domain_id = domain.id
            LEFT JOIN
                (
                    /* Create a "node" that has the fields we care about and
                     * also has a "fqdn" field.
                     * The fqdn requires that we fetch domain[node.domain_id]
                     * which, in turn, means that we need this inner select.
                     */
                    SELECT
                        nd.hostname AS hostname,
                        nd.system_id AS system_id,
                        nd.node_type AS node_type,
                        nd.owner_id AS user_id ,
                        nd.domain_id AS domain_id,
                        CONCAT(nd.hostname, '.', dom.name) AS fqdn,
                        nd.id AS id /* added in 2025 */
                    FROM maasserver_node AS nd
                    JOIN maasserver_domain AS dom ON
                        nd.domain_id = dom.id
                ) AS node ON (
                    /* We get the various node fields in the final result for
                     * any resource records that have an FQDN equal to the
                     * respective node.  Because of how names at the top of a
                     * domain are handled (we hide the fact from the user and
                     * put the node in the parent domain, but all the actual
                     * data lives in the child domain), we need to merge the
                     * two views of the world.
                     * If either this is the right node (node name and domain
                     * match, or dnsresource name is '@' and the node fqdn is
                     * the domain name), then we include the information about
                     * the node.
                     */
                    (
                        dnsresource.name = node.hostname AND
                        dnsresource.domain_id = node.domain_id
                    ) OR
                    (
                        dnsresource.name = '@' AND
                        node.fqdn = domain.name
                    )
                )
            WHERE
                /* The entries must be in this domain (though node.domain_id
                 * may be out-of-domain and that's OK.
                 * Additionally, if there is a CNAME and a node, then the node
                 * wins, and we drop the CNAME until the node no longer has the
                 * same name.
                 */
                (dnsresource.domain_id = {domain.id} OR node.fqdn IS NOT NULL) AND
                (dnsdata.rrtype != 'CNAME' OR node.fqdn IS NULL)
            ORDER BY
                dnsresource.name,
                dnsdata.rrtype,
                dnsdata.rrdata
            """
        # N.B.: The "node.hostname IS NULL" above is actually checking that
        # no node exists with the same name, in order to make sure that we do
        # not spill CNAME and other data.
        mapping = defaultdict(HostnameRRsetMapping)
        sql_query = text(sql_query)
        results = (await self.execute_stmt(sql_query)).all()
        for row in results:
            row = DnsDataMappingQueryResult(**row._asdict())
            if row.name == "@" and row.d_name != domain.name:
                row.name, row.d_name = row.d_name.split(".", 1)  # type: ignore
                # Since we don't allow more than one label in dnsresource
                # names, we should never ever be wrong in this assertion.
                assert row.d_name == domain.name, (
                    f"Invalid domain; expected {row.d_name} == {domain.name}"
                )
            entry = mapping[row.name]
            entry.node_type = row.node_type
            entry.system_id = row.system_id
            entry.user_id = row.user_id
            if with_node_id:
                entry.node_id = row.node_id
            if with_ids:
                entry.dnsresource_id = row.dnsresource_id
                rrtuple = (row.ttl, row.rrtype, row.rrdata, row.dnsdata_id)
            else:
                rrtuple = (row.ttl, row.rrtype, row.rrdata)
            entry.rrset.add(rrtuple)
        return mapping

    async def get_forwarded_domains(
        self,
    ) -> list[tuple[Domain, ForwardDNSServer]]:
        stmt = (
            select(
                DomainTable,
                ForwardDNSServerTable.c.id.label("fdns_id"),
                ForwardDNSServerTable.c.created.label("fdns_created"),
                ForwardDNSServerTable.c.updated.label("fdns_updated"),
                ForwardDNSServerTable.c.ip_address.label("fdns_ip_address"),
                ForwardDNSServerTable.c.port.label("fdns_port"),
            )
            .select_from(DomainTable)
            .join(
                ForwardDNSServerDomainsTable,
                ForwardDNSServerDomainsTable.c.domain_id == DomainTable.c.id,
            )
            .join(
                ForwardDNSServerTable,
                ForwardDNSServerTable.c.id
                == ForwardDNSServerDomainsTable.c.forwarddnsserver_id,
            )
            .filter(
                and_(
                    eq(DomainTable.c.authoritative, False),
                    ForwardDNSServerTable.c.id is not None,
                )
            )
        )

        rows = (await self.execute_stmt(stmt)).all()

        result = []

        for row in rows:
            row_dict = row._asdict()
            result.append(
                (
                    Domain(**row_dict),
                    ForwardDNSServer(
                        id=row_dict["fdns_id"],
                        created=row_dict["fdns_created"],
                        updated=row_dict["fdns_updated"],
                        ip_address=row_dict["fdns_ip_address"],
                        port=row_dict["fdns_port"],
                    ),
                )
            )

        return result
