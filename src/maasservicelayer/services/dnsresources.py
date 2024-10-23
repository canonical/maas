#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.ipaddress import IpAddressType
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.dnsresources import (
    DNSResourceClauseFactory,
    DNSResourceRepository,
    DNSResourceResourceBuilder,
)
from maasservicelayer.models.dnsresources import DNSResource
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.services._base import Service
from maasservicelayer.services.domains import DomainsService
from provisioningserver.utils.network import coerce_to_valid_hostname


class DNSResourcesService(Service):
    def __init__(
        self,
        connection: AsyncConnection,
        domains_service: DomainsService,
        dnsresource_repository: Optional[DNSResourceRepository] = None,
    ):
        super().__init__(connection)
        self.domains_service = domains_service
        self.dnsresource_repository = (
            dnsresource_repository
            if dnsresource_repository
            else DNSResourceRepository(connection)
        )

    async def get_or_create(
        self, **values: dict[str, Any]
    ) -> (DNSResource, bool):
        if "domain_id" not in values:
            default_domain = await self.domains_service.get_default_domain()
            values["domain_id"] = default_domain.id

        clause = None
        for k, v in values.items():
            match k:
                case "name":
                    name_clause = DNSResourceClauseFactory.with_name(v)
                    clause = (
                        name_clause
                        if not clause
                        else DNSResourceClauseFactory.and_clauses(
                            [clause, name_clause]
                        )
                    )
                case "domain_id":
                    domain_clause = DNSResourceClauseFactory.with_domain_id(v)
                    clause = (
                        domain_clause
                        if not clause
                        else DNSResourceClauseFactory.and_clauses(
                            [clause, domain_clause]
                        )
                    )

        dnsrr = await self.dnsresource_repository.get(QuerySpec(where=clause))
        if dnsrr is None:
            now = datetime.utcnow()
            resource = (
                DNSResourceResourceBuilder()
                .with_created(now)
                .with_updated(now)
            )
            for k, v in values.items():
                match k:
                    case "name":
                        resource = resource.with_name(v)
                    case "domain_id":
                        resource = resource.with_domain_id(v)

            dnsrr = await self.dnsresource_repository.create(resource.build())
            return (dnsrr, True)
        return (dnsrr, False)

    async def release_dynamic_hostname(
        self, ip: StaticIPAddress, but_not_for: Optional[DNSResource] = None
    ) -> None:
        if ip.ip is None or ip.alloc_type != IpAddressType.DISCOVERED.value:
            return

        default_domain = await self.domains_service.get_default_domain()

        resources = await self.dnsresource_repository.get_dnsresources_in_domain_for_ip(
            default_domain, ip
        )

        for dnsrr in resources:
            result = await self.dnsresource_repository.get_ips_for_dnsresource(
                dnsrr, discovered_only=True, matching=ip
            )

            ip_ids = [row.id for row in result]

            if ip.id in ip_ids:
                await self.dnsresource_repository.remove_ip_relation(dnsrr, ip)

            remaining_relations = (
                await self.dnsresource_repository.get_ips_for_dnsresource(
                    dnsrr
                )
            )
            if len(remaining_relations) == 0:
                await self.dnsresource_repository.delete(dnsrr.id)

    async def update_dynamic_hostname(
        self, ip: StaticIPAddress, hostname: str
    ) -> None:
        hostname = coerce_to_valid_hostname(hostname)

        await self.release_dynamic_hostname(ip)

        dnsrr, created = await self.get_or_create(name=hostname)
        if created:
            await self.dnsresource_repository.link_ip(dnsrr, ip)
        else:
            ips = await self.dnsresource_repository.get_ips_for_dnsresource(
                dnsrr,
            )
            dynamic_ips = (
                await self.dnsresource_repository.get_ips_for_dnsresource(
                    dnsrr, dynamic_only=True
                )
            )

            if len(ips) > len(dynamic_ips):  # has static IPs
                return

            if ip in dynamic_ips:
                return

            await self.dnsresource_repository.link_ip(dnsrr, ip)
