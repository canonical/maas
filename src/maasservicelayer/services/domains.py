#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from typing import List

from maascommon.enums.dns import DnsUpdateAction
from maasservicelayer.builders.domains import DomainBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.domains import DomainsRepository
from maasservicelayer.models.domains import Domain
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.dnspublications import DNSPublicationsService


class DomainsService(BaseService[Domain, DomainsRepository, DomainBuilder]):
    def __init__(
        self,
        context: Context,
        dnspublications_service: DNSPublicationsService,
        domains_repository: DomainsRepository,
    ):
        super().__init__(context, domains_repository)
        self.dnspublications_service = dnspublications_service

    async def post_create_hook(self, resource: Domain) -> None:
        if resource.authoritative:
            await self.dnspublications_service.create_for_config_update(
                source=f"added zone {resource.name}",
                action=DnsUpdateAction.RELOAD,
            )

    async def post_update_hook(
        self, old_resource: Domain, updated_resource: Domain
    ) -> None:
        source = None
        if old_resource.authoritative and not updated_resource.authoritative:
            source = f"removed zone {updated_resource.name}"
        elif not old_resource.authoritative and updated_resource.authoritative:
            source = f"added zone {updated_resource.name}"
        elif old_resource.authoritative and updated_resource.authoritative:
            changes = []
            if old_resource.name != updated_resource.name:
                changes.append(f"renamed to {updated_resource.name}")
            if old_resource.ttl != updated_resource.ttl:
                changes.append(f"ttl changed to {updated_resource.ttl}")
            if changes:
                source = f"zone {old_resource.name} " + " and ".join(changes)

        if source:
            await self.dnspublications_service.create_for_config_update(
                source=source,
                action=DnsUpdateAction.RELOAD,
            )

    async def post_update_many_hook(self, resources: List[Domain]) -> None:
        raise NotImplementedError("Not implemented yet.")

    async def post_delete_hook(self, resource: Domain) -> None:
        if resource.authoritative:
            await self.dnspublications_service.create_for_config_update(
                source=f"removed zone {resource.name}",
                action=DnsUpdateAction.RELOAD,
            )

    async def post_delete_many_hook(self, resources: List[Domain]) -> None:
        raise NotImplementedError("Not implemented yet.")

    async def get_default_domain(self) -> Domain:
        return await self.repository.get_default_domain()
