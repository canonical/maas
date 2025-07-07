# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from base64 import b64decode

from fastapi import Depends

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.boot_sources import (
    BootSourceFetchRequest,
)
from maasapiserver.v3.api.public.models.responses.boot_sources import (
    BootSourceFetchListResponse,
    BootSourceFetchResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.services import ServiceCollectionV3


class BootSourcesHandler(Handler):
    """BootSources API handler."""

    TAGS = ["BootSources"]

    @handler(
        path="/boot_sources:fetch",
        methods=["POST"],
        tags=TAGS,
        responses={
            200: {
                "model": BootSourceFetchListResponse,
            },
        },
        status_code=200,
        response_model_exclude_none=True,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def fetch_boot_sources(
        self,
        request: BootSourceFetchRequest,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> BootSourceFetchListResponse:
        # Base64 decode keyring data (if present) so we can write the bytes to file later.
        keyring_data_bytes = None
        if request.keyring_data:
            keyring_data_bytes = b64decode(request.keyring_data)

        boot_source_mapping = await services.boot_sources.fetch(
            request.url,
            keyring_path=request.keyring_path,
            keyring_data=keyring_data_bytes,
            validate_products=request.validate_products,
        )

        # The fetch method isn't paginated, so we return all items
        # in a single response.
        return BootSourceFetchListResponse(
            items=[
                BootSourceFetchResponse.from_model(boot_source)
                for boot_source in boot_source_mapping.items()
            ],
        )
