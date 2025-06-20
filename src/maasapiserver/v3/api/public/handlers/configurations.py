# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Depends
from starlette.requests import Request

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    NotFoundBodyResponse,
)
from maasapiserver.common.utils.http import get_remote_ip
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.configurations import (
    ConfigurationsFiltersParams,
    PublicConfigName,
    UpdateConfigurationRequest,
)
from maasapiserver.v3.api.public.models.responses.configurations import (
    ConfigurationResponse,
    ConfigurationsListResponse,
)
from maasapiserver.v3.auth.base import (
    check_permissions,
    get_authenticated_user,
)
from maascommon.enums.events import EventTypeEnum
from maascommon.events import EVENT_DETAILS_MAP
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.models.auth import AuthenticatedUser
from maasservicelayer.models.events import EndpointChoicesEnum
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

    @handler(
        path="/configurations/{name}",
        methods=["PUT"],
        tags=TAGS,
        responses={
            200: {"model": ConfigurationResponse},
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def set_configuration(
        self,
        request: Request,
        name: PublicConfigName,  # pyright: ignore [reportInvalidTypeForm]
        body_request: UpdateConfigurationRequest,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
        authenticated_user: AuthenticatedUser | None = Depends(  # noqa: B008
            get_authenticated_user
        ),
    ) -> ConfigurationResponse:
        assert (
            authenticated_user is not None
        )  # make pyright happy, since this endpoint requires authentication there is always a user
        config_name = name.value
        body_request.check_typing(config_name)
        await services.configurations.set(config_name, body_request.value)
        await services.events.record_event(
            event_type=EventTypeEnum.SETTINGS,
            event_action=EVENT_DETAILS_MAP[EventTypeEnum.SETTINGS].description,
            event_description=f"Updated configuration setting '{config_name}' to '{body_request.value}'.",
            user_agent=request.headers.get("user-agent", ""),
            ip_address=get_remote_ip(request),
            user=authenticated_user.username,
            endpoint=EndpointChoicesEnum.API,
        )
        return ConfigurationResponse(
            name=config_name, value=body_request.value
        )
