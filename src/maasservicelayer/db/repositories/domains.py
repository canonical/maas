#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from collections import defaultdict
from dataclasses import dataclass
from typing import Type

from sqlalchemy import select, Table, text
from sqlalchemy.sql.operators import eq

from maascommon.dns import HostnameRRsetMapping
from maascommon.enums.node import NodeTypeEnum
from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import DomainTable, GlobalDefaultTable
from maasservicelayer.models.domains import Domain


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

    async def get_hostname_dnsdata_mapping(
        self, domain_id: int, default_ttl: int, raw_ttl=False, with_ids=True
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
                row.name, row.d_name = row.d_name.split(".", 1)
                # Since we don't allow more than one label in dnsresource
                # names, we should never ever be wrong in this assertion.
                assert row.d_name == domain.name, (
                    f"Invalid domain; expected {row.d_name} == {domain.name}"
                )
            entry = mapping[row.name]
            entry.node_type = row.node_type
            entry.system_id = row.system_id
            entry.user_id = row.user_id
            if with_ids:
                entry.dnsresource_id = row.dnsresource_id
                rrtuple = (row.ttl, row.rrtype, row.rrdata, row.dnsdata_id)
            else:
                rrtuple = (row.ttl, row.rrtype, row.rrdata)
            entry.rrset.add(rrtuple)
        return mapping
