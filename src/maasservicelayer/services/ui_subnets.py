# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Sequence

from maascommon.utils.network import IPRangeStatistics
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.ui_subnets import UISubnetsRepository
from maasservicelayer.models.ui_subnets import UISubnet, UISubnetStatistics
from maasservicelayer.services.base import ReadOnlyService
from maasservicelayer.services.subnet_utilization import (
    V3SubnetUtilizationService,
)


class UISubnetsService(ReadOnlyService[UISubnet, UISubnetsRepository]):
    def __init__(
        self,
        context: Context,
        ui_subnets_repository: UISubnetsRepository,
        subnets_utilization_service: V3SubnetUtilizationService,
    ):
        super().__init__(context, ui_subnets_repository)
        self.subnets_utilization_service = subnets_utilization_service

    async def calculate_statistics_for_subnet(
        self, subnet: UISubnet
    ) -> UISubnet:
        ipset = await self.subnets_utilization_service.get_subnet_utilization(
            subnet.id
        )
        stats = IPRangeStatistics(ipset)
        statistics = UISubnetStatistics(
            **stats.render_json(include_suggestions=True)
        )
        subnet.statistics = statistics
        return subnet

    async def calculate_statistics_for_subnets(
        self, subnets: Sequence[UISubnet]
    ) -> Sequence[UISubnet]:
        for subnet in subnets:
            subnet = await self.calculate_statistics_for_subnet(subnet)
        return subnets
