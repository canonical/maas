# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Depends, Header, Response, status

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    NotFoundBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.query import PaginationParams
from maasapiserver.v3.api.public.models.requests.racks import RackRequest
from maasapiserver.v3.api.public.models.responses.agents import (
    AgentListResponse,
    AgentResponse,
)
from maasapiserver.v3.api.public.models.responses.base import (
    OPENAPI_ETAG_HEADER,
)
from maasapiserver.v3.api.public.models.responses.racks import (
    RackBootstrapTokenResponse,
    RackListResponse,
    RackResponse,
    RackWithSummaryListResponse,
    RackWithSummaryResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.agents import AgentsClauseFactory
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.services import ServiceCollectionV3


class RacksHandler(Handler):
    """Racks API handler."""

    TAGS = ["Racks"]

    @handler(
        path="/racks",
        methods=["GET"],
        tags=TAGS,
        responses={200: {"model": RackListResponse}},
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_racks(
        self,
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> RackListResponse:
        racks = await services.racks.list(
            page=pagination_params.page, size=pagination_params.size
        )
        return RackListResponse(
            items=[
                RackResponse.from_model(
                    rack=rack,
                    self_base_hyperlink=f"{V3_API_PREFIX}/racks",
                )
                for rack in racks.items
            ],
            total=racks.total,
            next=(
                f"{V3_API_PREFIX}/racks?"
                f"{pagination_params.to_next_href_format()}"
                if racks.has_next(
                    pagination_params.page, pagination_params.size
                )
                else None
            ),
        )

    @handler(
        path="/racks_with_summary",
        methods=["GET"],
        summary="List racks with a summary.",
        tags=TAGS,
        responses={200: {"model": RackWithSummaryListResponse}},
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_racks_with_summary(
        self,
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ):
        racks = await services.racks.list_with_summary(
            page=pagination_params.page, size=pagination_params.size
        )

        return RackWithSummaryListResponse(
            items=[
                RackWithSummaryResponse.from_model(
                    rack=rack,
                    self_base_hyperlink=f"{V3_API_PREFIX}/racks",
                )
                for rack in racks.items
            ],
            total=racks.total,
            next=(
                f"{V3_API_PREFIX}/racks_with_summary?"
                f"{pagination_params.to_next_href_format()}"
                if racks.has_next(
                    pagination_params.page, pagination_params.size
                )
                else None
            ),
        )

    @handler(
        path="/racks/{rack_id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": RackResponse,
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
    async def get_rack(
        self,
        rack_id: int,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> RackResponse:
        rack = await services.racks.get_by_id(rack_id)
        if rack is None:
            raise NotFoundException()
        response.headers["ETag"] = rack.etag()

        return RackResponse.from_model(
            rack=rack,
            self_base_hyperlink=f"{V3_API_PREFIX}/racks",
        )

    @handler(
        path="/racks",
        methods=["POST"],
        tags=TAGS,
        responses={
            201: {
                "model": RackResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
        },
        response_model_exclude_none=True,
        status_code=201,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def create_rack(
        self,
        rack_request: RackRequest,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> RackResponse:
        builder = rack_request.to_builder()
        rack = await services.racks.create(builder)
        response.headers["ETag"] = rack.etag()
        return RackResponse.from_model(
            rack=rack,
            self_base_hyperlink=f"{V3_API_PREFIX}/racks",
        )

    @handler(
        path="/racks/{rack_id}",
        methods=["PUT"],
        tags=TAGS,
        responses={
            200: {
                "model": RackResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def update_rack(
        self,
        rack_id: int,
        rack_request: RackRequest,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> RackResponse:
        builder = rack_request.to_builder()
        rack = await services.racks.update_by_id(rack_id, builder)
        response.headers["ETag"] = rack.etag()
        return RackResponse.from_model(
            rack=rack,
            self_base_hyperlink=f"{V3_API_PREFIX}/racks",
        )

    @handler(
        path="/racks/{rack_id}",
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
    async def delete_racks(
        self,
        rack_id: int,
        etag_if_match: str | None = Header(alias="if-match", default=None),
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        await services.racks.delete_by_id(rack_id, etag_if_match)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @handler(
        path="/racks/{rack_id}/tokens:generate",
        methods=["POST"],
        tags=TAGS,
        responses={
            200: {
                "model": RackBootstrapTokenResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def generate_rack_bootstrap_token(
        self,
        rack_id: int,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> RackBootstrapTokenResponse:
        rack = await services.racks.get_by_id(rack_id)
        if rack is None:
            raise NotFoundException()
        response.headers["ETag"] = rack.etag()

        token = await services.racks.generate_bootstrap_token(rack)

        return RackBootstrapTokenResponse.from_model(
            token=token,
        )

    @handler(
        path="/racks/{rack_id}/agents",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": AgentListResponse,
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
    async def list_rack_agents(
        self,
        rack_id: int,
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> AgentListResponse:
        agents = await services.agents.list(
            page=pagination_params.page,
            size=pagination_params.size,
            query=QuerySpec(where=AgentsClauseFactory.with_rack_id(rack_id)),
        )
        if not agents:
            raise NotFoundException()

        return AgentListResponse(
            items=[
                AgentResponse.from_model(
                    agent=agent,
                    self_base_hyperlink=f"{V3_API_PREFIX}/racks/{rack_id}/agents/",
                )
                for agent in agents.items
            ],
            total=agents.total,
            next=(
                f"{V3_API_PREFIX}/racks/{rack_id}/agents?"
                f"{pagination_params.to_next_href_format()}"
                if agents.has_next(
                    pagination_params.page, pagination_params.size
                )
                else None
            ),
        )

    @handler(
        path="/racks/{rack_id}/agents/{id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": AgentResponse,
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
    async def get_rack_agent(
        self,
        rack_id: int,
        id: int,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> AgentResponse:
        agent = await services.agents.get_one(
            QuerySpec(
                where=AgentsClauseFactory.and_clauses(
                    [
                        AgentsClauseFactory.with_id(id),
                        AgentsClauseFactory.with_rack_id(rack_id),
                    ]
                )
            )
        )
        if not agent:
            raise NotFoundException()

        response.headers["ETag"] = agent.etag()
        return AgentResponse.from_model(
            agent=agent,
            self_base_hyperlink=f"{V3_API_PREFIX}/racks/{rack_id}/agents/",
        )

    @handler(
        path="/racks/{rack_id}/agents/{id}",
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
    async def delete_rack_agent(
        self,
        rack_id: int,
        id: int,
        etag_if_match: str | None = Header(alias="if-match", default=None),
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        query = QuerySpec(
            where=AgentsClauseFactory.and_clauses(
                [
                    AgentsClauseFactory.with_id(id),
                    AgentsClauseFactory.with_rack_id(rack_id),
                ]
            )
        )
        await services.agents.delete_one(
            query=query,
            etag_if_match=etag_if_match,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
