#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import List

from maascommon.enums.dns import DnsUpdateAction
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.dnsdata import DNSDataRepository
from maasservicelayer.models.dnsdata import DNSData, DNSDataBuilder
from maasservicelayer.models.dnsresources import DNSResource
from maasservicelayer.models.domains import Domain
from maasservicelayer.services._base import BaseService
from maasservicelayer.services.dnspublications import DNSPublicationsService
from maasservicelayer.services.dnsresources import DNSResourcesService
from maasservicelayer.services.domains import DomainsService


class DNSDataService(BaseService[DNSData, DNSDataRepository, DNSDataBuilder]):
    def __init__(
        self,
        context: Context,
        dnspublications_service: DNSPublicationsService,
        dnsresources_service: DNSResourcesService,
        domains_service: DomainsService,
        dnsdata_repository: DNSDataRepository,
    ):
        super().__init__(context, dnsdata_repository)
        self.dnspublications_service = dnspublications_service
        self.dnsresources_service = dnsresources_service
        self.domains_service = domains_service

    def _get_ttl(
        self, dnsdata: DNSData, dnsresource: DNSResource, domain: Domain
    ) -> int:
        return (
            dnsdata.ttl
            if dnsdata.ttl
            else (
                dnsresource.address_ttl
                if dnsresource.address_ttl
                else domain.ttl if domain.ttl else 30
            )
        )

    async def post_create_hook(self, resource: DNSData) -> None:
        dnsresource = await self.dnsresources_service.get_by_id(
            resource.dnsresource_id
        )
        domain = await self.domains_service.get_by_id(dnsresource.domain_id)

        await self.dnspublications_service.create_for_config_update(
            source=f"added {resource.rrtype} to resource {dnsresource.name} on zone {domain.name}",
            action=DnsUpdateAction.INSERT,
            label=dnsresource.name,
            zone=domain.name,
            rtype=resource.rrtype,
            ttl=self._get_ttl(resource, dnsresource, domain),
            answer=resource.rrdata,
        )

    async def post_update_hook(
        self,
        _: DNSData,
        new_resource: DNSData,
    ) -> None:
        dnsresource = await self.dnsresources_service.get_by_id(
            new_resource.dnsresource_id,
        )
        domain = await self.domains_service.get_by_id(
            dnsresource.domain_id,
        )

        await self.dnspublications_service.create_for_config_update(
            source=f"updated {new_resource.rrtype} in resource {dnsresource.name} on zone {domain.name}",
            action=DnsUpdateAction.UPDATE,
            label=dnsresource.name,
            zone=domain.name,
            rtype=new_resource.rrtype,
            ttl=self._get_ttl(new_resource, dnsresource, domain),
            answer=new_resource.rrdata,
        )

    async def post_update_many_hook(self, resources: List[DNSData]) -> None:
        raise NotImplementedError("Not implemented yet.")

    async def post_delete_hook(self, resource: DNSData) -> None:
        dnsresource = await self.dnsresources_service.get_by_id(
            resource.dnsresource_id,
        )
        domain = await self.domains_service.get_by_id(
            dnsresource.domain_id,
        )

        await self.dnspublications_service.create_for_config_update(
            source=f"removed {resource.rrtype} from resource {dnsresource.name} on zone {domain.name}",
            action=DnsUpdateAction.DELETE,
            label=dnsresource.name,
            zone=domain.name,
            rtype=resource.rrtype,
            ttl=self._get_ttl(resource, dnsresource, domain),
            answer=resource.rrdata,
        )

    async def post_delete_many_hook(
        self, resources: List[DNSResource]
    ) -> None:
        raise NotImplementedError("Not implemented yet.")
