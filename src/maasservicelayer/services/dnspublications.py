#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime

from maascommon.enums.dns import DnsUpdateAction
from maasservicelayer.builders.dnspublications import DNSPublicationBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.dnspublications import (
    DNSPublicationRepository,
)
from maasservicelayer.models.dnspublications import DNSPublication
from maasservicelayer.services.base import BaseService
from maasservicelayer.utils.date import utcnow


class MaxSerialException(Exception):
    pass


class DNSPublicationsService(
    BaseService[
        DNSPublication, DNSPublicationRepository, DNSPublicationBuilder
    ]
):
    def __init__(
        self,
        context: Context,
        dnspublication_repository: DNSPublicationRepository,
    ):
        super().__init__(context, dnspublication_repository)

    async def create_for_config_update(
        self,
        source: str,
        action: DnsUpdateAction,
        label: str | None = None,
        rtype: str | None = None,
        zone: str | None = None,
        ttl: int | None = None,
        answer: str | None = None,
        timestamp: datetime | None = None,
    ) -> DNSPublication:
        update = None
        if action == DnsUpdateAction.RELOAD:
            update = DnsUpdateAction.RELOAD
        else:
            update = f"{action} {zone} {label} {rtype}"
            if ttl:
                update += f" {ttl}"
            if answer:
                update += f" {answer}"

        next_serial = await self.repository.get_next_serial()

        if not timestamp:
            timestamp = utcnow()

        return await self.create(
            DNSPublicationBuilder(
                source=source,
                update=update,
                serial=next_serial,
                created=timestamp,
            )
        )
