# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Depends
from starlette.responses import Response

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    NotFoundBodyResponse,
    NotFoundResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.responses.configurations import (
    ConfigurationResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.models.configurations import ConfigFactory
from maasservicelayer.services import ServiceCollectionV3


class ConfigurationsHandler(Handler):
    """Configurations API handler."""

    TAGS = ["Configurations"]

    @handler(
        path="/configurations/{name}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {"model": ConfigurationResponse},
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def get_configuration(
        self,
        name: str,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        configuration = await services.configurations.get(name)
        try:
            # Validate that the configuration being accessed is well known and public.
            ConfigFactory.parse_public_config(name, configuration)
        except ValueError:
            return NotFoundResponse()
        return ConfigurationResponse(name=name, value=configuration)
