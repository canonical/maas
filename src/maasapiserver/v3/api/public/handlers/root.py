# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Depends
from pydantic import BaseModel

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.v3.api import services
from maasservicelayer.services import ServiceCollectionV3


class RootGetResponse(BaseModel):
    """Root handler response."""

    fips_active: bool


class RootHandler(Handler):
    """Root API handler."""

    @handler(path="/", methods=["GET"], include_in_schema=False)
    async def get(
        self,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> RootGetResponse:
        status = await services.fips.get_fips_status()
        return RootGetResponse(fips_active=status.fips_enabled)
