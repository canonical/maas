# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Depends

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    ValidationErrorBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.events import (
    EventsFiltersParams,
)
from maasapiserver.v3.api.public.models.requests.query import PaginationParams
from maasapiserver.v3.api.public.models.responses.events import (
    EventResponse,
    EventsListResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.services import ServiceCollectionV3


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
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        filters: EventsFiltersParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> EventsListResponse:
        events = await services.events.list(
            page=pagination_params.page,
            size=pagination_params.size,
            query=QuerySpec(where=filters.to_clause()),
        )
        next_link = None
        if events.has_next(pagination_params.page, pagination_params.size):
            next_link = (
                f"{V3_API_PREFIX}/events?"
                f"{pagination_params.to_next_href_format()}"
            )
            if query_filters := filters.to_href_format():
                next_link += f"&{query_filters}"
        return EventsListResponse(
            items=[
                EventResponse.from_model(event, f"{V3_API_PREFIX}/events")
                for event in events.items
            ],
            total=events.total,
            next=next_link,
        )
