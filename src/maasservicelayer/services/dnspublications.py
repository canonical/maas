#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from typing import Optional

from maascommon.enums.dns import DnsUpdateAction
from maascommon.workflows.dns import (
    CONFIGURE_DNS_WORKFLOW_NAME,
    ConfigureDNSParam,
    merge_configure_dns_params,
)
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.base import CreateOrUpdateResource
from maasservicelayer.db.repositories.dnspublications import (
    DNSPublicationRepository,
    DNSPublicationResourceBuilder,
)
from maasservicelayer.models.dnspublications import DNSPublication
from maasservicelayer.services._base import Service
from maasservicelayer.services.temporal import TemporalService
from maasservicelayer.utils.date import utcnow


class MaxSerialException(Exception):
    pass


class DNSPublicationsService(Service):
    def __init__(
        self,
        context: Context,
        temporal_service: TemporalService,
        dnspublication_repository: Optional[DNSPublicationRepository] = None,
    ):
        super().__init__(context)
        self.dnspublication_repository = (
            dnspublication_repository
            if dnspublication_repository
            else DNSPublicationRepository(context)
        )
        self.temporal_service = temporal_service

    async def create(self, resource: CreateOrUpdateResource) -> DNSPublication:
        return await self.dnspublication_repository.create(resource)

    async def create_for_config_update(
        self,
        source: str,
        action: DnsUpdateAction,
        label: Optional[str] = None,
        rtype: Optional[str] = None,
        zone: Optional[str] = None,
        ttl: Optional[int] = None,
        answer: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> DNSPublication:
        latest_serial = (
            await self.dnspublication_repository.get_latest_serial()
        )

        update = None
        if action == DnsUpdateAction.RELOAD:
            update = DnsUpdateAction.RELOAD
        else:
            update = f"{action} {zone} {label} {rtype}"
            if ttl:
                update += f" {ttl}"
            if answer:
                update += f" {answer}"

        next_serial = None
        if latest_serial < (2**63) - 1:
            next_serial = latest_serial + 1
        else:
            raise MaxSerialException("next serial exceeds max int value")

        if not timestamp:
            timestamp = utcnow()

        self.temporal_service.register_or_update_workflow_call(
            CONFIGURE_DNS_WORKFLOW_NAME,
            ConfigureDNSParam(
                need_full_reload=action == DnsUpdateAction.RELOAD
            ),
            parameter_merge_func=merge_configure_dns_params,
            wait=False,
        )

        return await self.create(
            DNSPublicationResourceBuilder()
            .with_source(source)
            .with_update(update)
            .with_serial(next_serial)
            .with_created(timestamp)
            .with_updated(timestamp)
            .build()
        )

    async def get_publications_since_serial(
        self, serial: int
    ) -> list[DNSPublication]:
        return (
            await self.dnspublication_repository.get_publications_since_serial(
                serial
            )
        )
