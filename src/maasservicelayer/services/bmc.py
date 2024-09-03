#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.db.repositories.bmc import BmcRepository
from maasservicelayer.services._base import Service


class BmcService(Service):
    def __init__(
        self,
        connection: AsyncConnection,
        bmc_repository: BmcRepository | None = None,
    ):
        super().__init__(connection)
        self.bmc_repository = (
            bmc_repository if bmc_repository else BmcRepository(connection)
        )

    async def move_to_zone(self, old_zone_id: int, new_zone_id: int) -> None:
        """
        Move all the BMC from 'old_zone_id' to 'new_zone_id'.
        """
        return await self.bmc_repository.move_to_zone(old_zone_id, new_zone_id)
