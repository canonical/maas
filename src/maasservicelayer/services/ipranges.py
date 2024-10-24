#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from pydantic import IPvAnyAddress
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.db.repositories.ipranges import IPRangesRepository
from maasservicelayer.models.ipranges import IPRange
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services._base import Service


class IPRangesService(Service):
    def __init__(
        self,
        connection: AsyncConnection,
        ipranges_repository: Optional[IPRangesRepository] = None,
    ):
        super().__init__(connection)
        self.ipranges_repository = (
            ipranges_repository
            if ipranges_repository
            else IPRangesRepository(connection)
        )

    async def get_dynamic_range_for_ip(
        self, subnet: Subnet, ip: IPvAnyAddress
    ) -> IPRange | None:
        return await self.ipranges_repository.get_dynamic_range_for_ip(
            subnet, ip
        )
