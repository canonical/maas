#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Depends, Response

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.v3.api import services
from maasapiserver.v3.api.internal.models.requests.leases import (
    LeaseInfoRequest,
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
        lease_info_request: LeaseInfoRequest,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        await services.leases.store_lease_info(
            Lease(
                action=lease_info_request.action,
                ip_family=IpAddressFamily(lease_info_request.ip_family),
                hostname=lease_info_request.hostname,
                mac=lease_info_request.mac,
                ip=lease_info_request.ip,
                timestamp_epoch=lease_info_request.timestamp,
                lease_time_seconds=lease_info_request.lease_time,
            )
        )
