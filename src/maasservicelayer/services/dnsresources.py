#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from maascommon.enums.ipaddress import IpAddressType
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.base import CreateOrUpdateResource
from maasservicelayer.db.repositories.dnsresources import (
    DNSResourceClauseFactory,
    DNSResourceRepository,
    DNSResourceResourceBuilder,
)
from maasservicelayer.models.dnsresources import DNSResource
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.services._base import Service
from maasservicelayer.services.domains import DomainsService
from maasservicelayer.utils.date import utcnow
from provisioningserver.utils.network import coerce_to_valid_hostname


class DNSResourcesService(Service):
    def __init__(
        self,
        context: Context,
        domains_service: DomainsService,
        dnsresource_repository: Optional[DNSResourceRepository] = None,
    ):
        super().__init__(context)
        self.domains_service = domains_service
        self.dnsresource_repository = (
            dnsresource_repository
            if dnsresource_repository
            else DNSResourceRepository(context)
        )

    async def get_one(self, query: QuerySpec) -> DNSResource | None:
        return await self.dnsresource_repository.get_one(query=query)

    async def create(self, resource: CreateOrUpdateResource) -> DNSResource:
        return await self.dnsresource_repository.create(resource=resource)

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

        dnsrr = await self.get_one(
            query=QuerySpec(where=DNSResourceClauseFactory.with_name(hostname))
        )
        if not dnsrr:
            now = utcnow()
            resource = (
                DNSResourceResourceBuilder()
                .with_name(hostname)
                .with_domain_id(
                    (await self.domains_service.get_default_domain()).id
                )
                .with_created(now)
                .with_updated(now)
                .build()
            )
            dnsrr = await self.create(resource=resource)
            await self.dnsresource_repository.link_ip(dnsrr, ip)
        else:
            ips = await self.dnsresource_repository.get_ips_for_dnsresource(
                dnsrr
            )
            dynamic_ips = (
                await self.dnsresource_repository.get_ips_for_dnsresource(
                    dnsrr, discovered_only=True
                )
            )

            if len(ips) > len(dynamic_ips):  # has static IPs
                return

            if ip in dynamic_ips:
                return

            await self.dnsresource_repository.link_ip(dnsrr, ip)
