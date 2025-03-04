#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import List

from fastapi import Depends, Response

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.v3.api import services
from maasapiserver.v3.api.internal.models.requests.leases import (
    LeaseInfoRequest,
    LeaseIPFamily,
)
from maascommon.enums.ipaddress import IpAddressFamily
from maasservicelayer.models.leases import Lease
from maasservicelayer.services import ServiceCollectionV3


class LeasesHandler(Handler):
    @handler(
        path="/leases",
        methods=["POST"],
        responses={
            204: {},
        },
        status_code=204,
    )
    async def store_lease_info(
        self,
        response: Response,
        leases_info_request: List[LeaseInfoRequest],
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        for lease_info_request in leases_info_request:
            await services.leases.store_lease_info(
                Lease(
                    action=lease_info_request.action,
                    ip_family=(
                        IpAddressFamily.IPV4
                        if lease_info_request.ip_family == LeaseIPFamily.IPV4
                        else IpAddressFamily.IPV6
                    ),
                    hostname=lease_info_request.hostname,
                    mac=lease_info_request.mac,
                    ip=lease_info_request.ip,
                    timestamp_epoch=lease_info_request.timestamp,
                    lease_time_seconds=lease_info_request.lease_time,
                )
            )
