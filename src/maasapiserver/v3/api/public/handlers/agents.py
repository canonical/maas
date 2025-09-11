# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Depends, Header, Response, status

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    NotFoundBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.query import PaginationParams
from maasapiserver.v3.api.public.models.responses.agents import (
    AgentResponse,
    AgentsListResponse,
)
from maasapiserver.v3.api.public.models.responses.base import (
    OPENAPI_ETAG_HEADER,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.services import ServiceCollectionV3


class AgentsHandler(Handler):
    """Agent API handler."""

    TAGS = ["Agents"]

    @handler(
        path="/agents/{agent_id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": AgentResponse,  # AgentResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def get_agent(
        self,
        agent_id: int,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> AgentResponse:
        agent = await services.agents.get_by_id(agent_id)
        if agent is None:
            raise NotFoundException()
        response.headers["ETag"] = agent.etag()
        return AgentResponse.from_model(
            agent=agent,
            self_base_hyperlink=f"{V3_API_PREFIX}/boot_sources",
        )

    @handler(
        path="/agents",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": AgentsListResponse,
            }
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_agents(
        self,
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> AgentsListResponse:
        agents = await services.agents.list(
            page=pagination_params.page, size=pagination_params.size
        )
        return AgentsListResponse(
            items=[
                AgentResponse.from_model(
                    agent=agent,
                    self_base_hyperlink=f"{V3_API_PREFIX}/agents",
                )
                for agent in agents.items
            ],
            total=agents.total,
            next=(
                f"{V3_API_PREFIX}/agents?"
                f"{pagination_params.to_next_href_format()}"
                if agents.has_next(
                    pagination_params.page, pagination_params.size
                )
                else None
            ),
        )

    @handler(
        path="/agents/{agent_id}",
        methods=["DELETE"],
        tags=TAGS,
        responses={
            204: {},
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=204,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def delete_agent(
        self,
        agent_id: int,
        etag_if_match: str | None = Header(alias="if-match", default=None),
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        await services.agents.delete_by_id(agent_id, etag_if_match)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
