#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
import re
from typing import List

from maascommon.dns import HostnameRRsetMapping
from maascommon.enums.dns import DnsUpdateAction
from maasservicelayer.builders.domains import DomainBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.domains import DomainsRepository
from maasservicelayer.exceptions.catalog import (
    BadRequestException,
    BaseExceptionDetail,
    ValidationException,
)
from maasservicelayer.exceptions.constants import (
    CANNOT_DELETE_DEFAULT_DOMAIN_VIOLATION_TYPE,
)
from maasservicelayer.models.domains import Domain
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.configurations import ConfigurationsService
from maasservicelayer.services.dnspublications import DNSPublicationsService

# Labels are at most 63 octets long, and a name can be many of them
LABEL = r"[a-zA-Z0-9]([-a-zA-Z0-9]{0,62}[a-zA-Z0-9]){0,1}"
NAMESPEC = rf"({LABEL}[.])*{LABEL}[.]?"


class DomainsService(BaseService[Domain, DomainsRepository, DomainBuilder]):
    def __init__(
        self,
        context: Context,
        configurations_service: ConfigurationsService,
        dnspublications_service: DNSPublicationsService,
        domains_repository: DomainsRepository,
    ):
        super().__init__(context, domains_repository)
        self.dnspublications_service = dnspublications_service
        self.configurations_service = configurations_service

    async def pre_create_hook(self, builder: DomainBuilder) -> None:
        # Same name validation as maasserver.models.domain.validate_domain_name
        namespec = re.compile(f"^{NAMESPEC}$")
        name = builder.name
        assert isinstance(name, str)
        if len(name) > 255:
            raise ValidationException.build_for_field(
                field="name",
                message="Domain name cannot exceed 255 characters.",
            )
        if not namespec.match(name):
            disallowed_chars = re.sub("[a-zA-Z0-9-.]*", "", name)
            if disallowed_chars:
                raise ValueError("Domain name contains invalid characters.")
            raise ValueError("Invalid domain name.")
        if name == await self.configurations_service.get(
            "maas_internal_domain"
        ):
            raise ValueError(
                "Domain name cannot duplicate MAAS internal domain."
            )

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

    async def pre_delete_hook(self, resource: Domain) -> None:
        default_domain = await self.get_default_domain()
        if resource.id == default_domain.id:
            raise BadRequestException(
                details=[
                    BaseExceptionDetail(
                        type=CANNOT_DELETE_DEFAULT_DOMAIN_VIOLATION_TYPE,
                        message="The default domain cannot be deleted.",
                    )
                ]
            )

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

    async def get_hostname_dnsdata_mapping(
        self, domain_id: int, raw_ttl=False, with_ids=True
    ) -> dict[str, HostnameRRsetMapping]:
        default_ttl = await self.configurations_service.get(
            "default_dns_ttl", default=30
        )
        return await self.repository.get_hostname_dnsdata_mapping(
            domain_id, default_ttl, raw_ttl, with_ids
        )
