#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import List, Optional

from maascommon.enums.dns import DnsUpdateAction
from maascommon.enums.ipaddress import IpAddressType
from maascommon.utils.network import coerce_to_valid_hostname
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.dnsresources import (
    DNSResourceClauseFactory,
    DNSResourceRepository,
)
from maasservicelayer.db.repositories.domains import DomainsClauseFactory
from maasservicelayer.models.dnsresources import (
    DNSResource,
    DNSResourceBuilder,
)
from maasservicelayer.models.domains import Domain
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.services._base import BaseService
from maasservicelayer.services.dnspublications import DNSPublicationsService
from maasservicelayer.services.domains import DomainsService

DEFAULT_DNSRESOURCE_TTL = 30


class DNSResourcesService(
    BaseService[DNSResource, DNSResourceRepository, DNSResourceBuilder]
):
    def __init__(
        self,
        context: Context,
        domains_service: DomainsService,
        dnspublications_service: DNSPublicationsService,
        dnsresource_repository: DNSResourceRepository,
    ):
        super().__init__(context, dnsresource_repository)
        self.domains_service = domains_service
        self.dnspublications_service = dnspublications_service

    def _get_ttl(self, dnsresource: DNSResource, domain: Domain) -> int:
        return (
            dnsresource.address_ttl
            if dnsresource.address_ttl
            else (domain.ttl if domain.ttl else DEFAULT_DNSRESOURCE_TTL)
        )

    async def post_create_hook(self, resource: DNSResource) -> None:
        domain = await self.domains_service.get_one(
            QuerySpec(where=DomainsClauseFactory.with_id(resource.domain_id))
        )
        await self.dnspublications_service.create_for_config_update(
            source=f"zone {domain.name} added resource {resource.name}",
            action=DnsUpdateAction.INSERT_NAME,
            label=resource.name,
            rtype="A",
            zone=domain.name,
        )

        return

    async def post_update_hook(
        self, old_resource: DNSResource, updated_resource: DNSResource
    ) -> None:
        old_domain = await self.domains_service.get_one(
            query=QuerySpec(
                where=DNSResourceClauseFactory.with_domain_id(
                    old_resource.domain_id
                )
            )
        )

        domain = await self.domains_service.get_one(
            query=QuerySpec(
                where=DomainsClauseFactory.with_id(updated_resource.domain_id)
            )
        )

        if old_domain.id != domain.id:
            await self.dnspublications_service.create_for_config_update(
                source=f"zone {old_domain.name} removed resource {old_resource.name}",
                action=DnsUpdateAction.DELETE,
                label=old_resource.name,
                rtype="A",
                zone=old_domain.name,
            )
            await self.dnspublications_service.create_for_config_update(
                source=f"zone {domain.name} added resource {updated_resource.name}",
                action=DnsUpdateAction.INSERT_NAME,
                label=updated_resource.name,
                rtype="A",
                zone=domain.name,
            )
        else:
            await self.dnspublications_service.create_for_config_update(
                source=f"zone {domain.name} updated resource {updated_resource.name}",
                action=DnsUpdateAction.UPDATE,
                label=updated_resource.name,
                rtype="A",
                zone=domain.name,
                ttl=self._get_ttl(updated_resource, domain),
            )

        return

    async def post_update_many_hook(
        self, resources: List[DNSResource]
    ) -> None:
        raise NotImplementedError("Not implemented yet.")

    async def post_delete_hook(self, resource: DNSResource) -> None:
        domain = await self.domains_service.get_one(
            query=QuerySpec(
                where=DomainsClauseFactory.with_id(resource.domain_id)
            )
        )

        await self.dnspublications_service.create_for_config_update(
            source=f"zone {domain.name} removed resource {resource.name}",
            action=DnsUpdateAction.DELETE,
            label=resource.name,
            rtype="A",
            zone=domain.name,
        )
        return

    async def post_delete_many_hook(
        self, resources: List[DNSResource]
    ) -> None:
        raise NotImplementedError("Not implemented yet.")

    async def release_dynamic_hostname(
        self, ip: StaticIPAddress, but_not_for: Optional[DNSResource] = None
    ) -> None:
        if ip.ip is None or ip.alloc_type != IpAddressType.DISCOVERED.value:
            return

        default_domain = await self.domains_service.get_default_domain()

        resources = await self.repository.get_dnsresources_in_domain_for_ip(
            default_domain, ip
        )

        for dnsrr in resources:
            result = await self.repository.get_ips_for_dnsresource(
                dnsrr, discovered_only=True, matching=ip
            )

            ip_ids = [row.id for row in result]

            if ip.id in ip_ids:
                await self.repository.remove_ip_relation(dnsrr, ip)

            remaining_relations = (
                await self.repository.get_ips_for_dnsresource(dnsrr)
            )
            if len(remaining_relations) == 0:
                await self.repository.delete_by_id(dnsrr.id)

                await self.dnspublications_service.create_for_config_update(
                    source=f"zone {default_domain.name} removed resource {dnsrr.name}",
                    action=DnsUpdateAction.DELETE,
                    label=dnsrr.name,
                    rtype="AAAA" if ip.ip.version == 6 else "A",
                )
            else:
                await self.dnspublications_service.create_for_config_update(
                    source=f"ip {ip.ip} unlinked from resource {dnsrr.name} on zone {default_domain.name}",
                    action=DnsUpdateAction.DELETE,
                    label=dnsrr.name,
                    rtype="AAAA" if ip.ip.version == 6 else "A",
                    ttl=self._get_ttl(dnsrr, default_domain),
                    answer=str(ip.ip),
                )

    async def update_dynamic_hostname(
        self, ip: StaticIPAddress, hostname: str
    ) -> None:
        hostname = coerce_to_valid_hostname(hostname)

        await self.release_dynamic_hostname(ip)

        domain = await self.domains_service.get_default_domain()

        dnsrr = await self.get_one(
            query=QuerySpec(where=DNSResourceClauseFactory.with_name(hostname))
        )
        if not dnsrr:
            dnsrr = await self.create(
                builder=DNSResourceBuilder(
                    name=hostname,
                    domain_id=domain.id,
                )
            )
            await self.repository.link_ip(dnsrr, ip)
            # Here we link an IP after the dnsresource was create,
            # so we create the DNSPublication here instead of in create()
            await self.dnspublications_service.create_for_config_update(
                source=f"ip {ip.ip} linked to resource {dnsrr.name} on zone {domain.name}",
                action=DnsUpdateAction.INSERT,
                label=dnsrr.name,
                rtype="AAAA" if ip.ip.version == 6 else "A",
                ttl=self._get_ttl(dnsrr, domain),
                zone=domain.name,
                answer=str(ip.ip),
            )
        else:
            ips = await self.repository.get_ips_for_dnsresource(dnsrr)
            dynamic_ips = await self.repository.get_ips_for_dnsresource(
                dnsrr, discovered_only=True
            )

            if len(ips) > len(dynamic_ips):  # has static IPs
                return

            if ip in dynamic_ips:
                return

            await self.repository.link_ip(dnsrr, ip)
            await self.dnspublications_service.create_for_config_update(
                source=f"ip {ip.ip} linked to resource {dnsrr.name} on zone {domain.name}",
                action=DnsUpdateAction.INSERT,
                label=dnsrr.name,
                rtype="AAAA" if ip.ip.version == 6 else "A",
                ttl=self._get_ttl(dnsrr, domain),
                zone=domain.name,
                answer=str(ip.ip),
            )
