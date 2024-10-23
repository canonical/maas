#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Depends, Response

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.v3.api import services
from maasapiserver.v3.api.internal.models.requests.leases import (
    LeaseInfoRequest,
)
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
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        await services.leases.store_lease_info(lease_info_request)
