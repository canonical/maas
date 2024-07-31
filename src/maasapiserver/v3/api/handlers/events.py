# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Depends, Response

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    ValidationErrorBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.models.requests.events import EventsFiltersParams
from maasapiserver.v3.api.models.requests.query import TokenPaginationParams
from maasapiserver.v3.api.models.responses.events import EventsListResponse
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.auth.jwt import UserRole
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.services import ServiceCollectionV3


class EventsHandler(Handler):
    """Events API handler."""

    TAGS = ["Events"]

    @handler(
        path="/events",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": EventsListResponse,
            },
            422: {"model": ValidationErrorBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_events(
        self,
        token_pagination_params: TokenPaginationParams = Depends(),
        filters: EventsFiltersParams = Depends(),
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        events = await services.events.list(
            token=token_pagination_params.token,
            size=token_pagination_params.size,
            query=filters.to_query(),
        )
        return EventsListResponse(
            items=[
                event.to_response(f"{V3_API_PREFIX}/events")
                for event in events.items
            ],
            next=(
                f"{V3_API_PREFIX}/events?"
                f"{TokenPaginationParams.to_href_format(events.next_token, token_pagination_params.size)}"
                if events.next_token
                else None
            ),
        )
