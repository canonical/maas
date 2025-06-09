# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Depends

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    NotFoundBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.configurations import (
    ConfigurationsFiltersParams,
    PublicConfigName,
)
from maasapiserver.v3.api.public.models.responses.configurations import (
    ConfigurationResponse,
    ConfigurationsListResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.services import ServiceCollectionV3


class ConfigurationsHandler(Handler):
    """Configurations API handler."""

    TAGS = ["Configurations"]

    @handler(
        path="/configurations",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {"model": ConfigurationsListResponse},
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def get_configurations(
        self,
        filters: ConfigurationsFiltersParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> ConfigurationsListResponse:
        configurations = await services.configurations.get_many(
            filters.get_names()
        )
        return ConfigurationsListResponse(
            items=[
                ConfigurationResponse(
                    name=configuration_name, value=configuration_value
                )
                for configuration_name, configuration_value in configurations.items()
            ]
        )

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
        name: PublicConfigName,  # pyright: ignore [reportInvalidTypeForm]
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> ConfigurationResponse:
        configuration = await services.configurations.get(name.value)
        return ConfigurationResponse(name=name.value, value=configuration)
