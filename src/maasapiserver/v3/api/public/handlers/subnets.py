# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Union

from fastapi import Depends, Header, Response, status

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    NotFoundBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.query import PaginationParams
from maasapiserver.v3.api.public.models.requests.subnets import SubnetRequest
from maasapiserver.v3.api.public.models.requests.ui_subnets import (
    UISubnetFiltersParams,
    UISubnetOrderByQueryFilter,
    UISubnetsFreeTextSearchQueryParam,
)
from maasapiserver.v3.api.public.models.responses.base import (
    OPENAPI_ETAG_HEADER,
)
from maasapiserver.v3.api.public.models.responses.subnets import (
    SubnetResponse,
    SubnetsListResponse,
)
from maasapiserver.v3.api.public.models.responses.ui_subnets import (
    UISubnetResponse,
    UISubnetsListResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX, V3_API_UI_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.db.filters import ClauseFactory, QuerySpec
from maasservicelayer.db.repositories.subnets import SubnetClauseFactory
from maasservicelayer.db.repositories.vlans import VlansClauseFactory
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    NotFoundException,
)
from maasservicelayer.exceptions.constants import (
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
)
from maasservicelayer.services import ServiceCollectionV3


class SubnetsHandler(Handler):
    """Subnets API handler."""

    TAGS = ["Subnets"]

    @handler(
        path="/fabrics/{fabric_id}/vlans/{vlan_id}/subnets",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {"model": SubnetsListResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_fabric_vlan_subnets(
        self,
        fabric_id: int,
        vlan_id: int,
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> SubnetsListResponse:
        vlan_exists = await services.vlans.exists(
            QuerySpec(
                where=VlansClauseFactory.and_clauses(
                    [
                        VlansClauseFactory.with_id(vlan_id),
                        VlansClauseFactory.with_fabric_id(fabric_id),
                    ]
                )
            )
        )
        if not vlan_exists:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                        message="Could not find VLAN {vlan_id} in fabric {fabric_id}",
                    )
                ]
            )
        query = QuerySpec(
            where=SubnetClauseFactory.and_clauses(
                [
                    SubnetClauseFactory.with_fabric_id(fabric_id),
                    SubnetClauseFactory.with_vlan_id(vlan_id),
                ]
            )
        )
        subnets = await services.subnets.list(
            page=pagination_params.page,
            size=pagination_params.size,
            query=query,
        )
        return SubnetsListResponse(
            items=[
                SubnetResponse.from_model(
                    subnet=subnet,
                    self_base_hyperlink=f"{V3_API_PREFIX}/fabrics/{fabric_id}/vlans/{vlan_id}/subnets",
                )
                for subnet in subnets.items
            ],
            total=subnets.total,
            next=(
                f"{V3_API_PREFIX}/fabrics/{fabric_id}/vlans/{vlan_id}/subnets?"
                f"{pagination_params.to_next_href_format()}"
                if subnets.has_next(
                    pagination_params.page, pagination_params.size
                )
                else None
            ),
        )

    @handler(
        path="/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": SubnetResponse,
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
    async def get_fabric_vlan_subnet(
        self,
        fabric_id: int,
        vlan_id: int,
        subnet_id: int,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> SubnetResponse:
        subnet = await services.subnets.get_one(
            query=QuerySpec(
                where=SubnetClauseFactory.and_clauses(
                    [
                        SubnetClauseFactory.with_id(subnet_id),
                        SubnetClauseFactory.with_vlan_id(vlan_id),
                        SubnetClauseFactory.with_fabric_id(fabric_id),
                    ]
                )
            )
        )
        if not subnet:
            raise NotFoundException()

        response.headers["ETag"] = subnet.etag()
        return SubnetResponse.from_model(
            subnet=subnet,
            self_base_hyperlink=f"{V3_API_PREFIX}/fabrics/{fabric_id}/vlans/{vlan_id}/subnets",
        )

    @handler(
        path="/fabrics/{fabric_id}/vlans/{vlan_id}/subnets",
        methods=["POST"],
        tags=TAGS,
        responses={
            201: {
                "model": SubnetResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=201,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def create_fabric_vlan_subnet(
        self,
        fabric_id: int,
        vlan_id: int,
        subnet_request: SubnetRequest,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> SubnetResponse:
        vlan_exists = await services.vlans.exists(
            QuerySpec(
                where=VlansClauseFactory.and_clauses(
                    [
                        VlansClauseFactory.with_id(vlan_id),
                        VlansClauseFactory.with_fabric_id(fabric_id),
                    ]
                )
            )
        )
        if not vlan_exists:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                        message="Could not find VLAN {vlan_id} in fabric {fabric_id}",
                    )
                ]
            )
        builder = subnet_request.to_builder(vlan_id=vlan_id)
        subnet = await services.subnets.create(builder=builder)
        response.headers["ETag"] = subnet.etag()
        return SubnetResponse.from_model(
            subnet=subnet,
            self_base_hyperlink=f"{V3_API_PREFIX}/fabrics/{fabric_id}/vlans/{vlan_id}/subnets",
        )

    @handler(
        path="/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{id}",
        methods=["PUT"],
        tags=TAGS,
        responses={
            200: {
                "model": SubnetResponse,
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
    async def update_fabric_vlan_subnet(
        self,
        fabric_id: int,
        vlan_id: int,
        id: int,
        subnet_request: SubnetRequest,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> SubnetResponse:
        query = QuerySpec(
            where=SubnetClauseFactory.and_clauses(
                [
                    SubnetClauseFactory.with_id(id),
                    SubnetClauseFactory.with_vlan_id(vlan_id),
                    SubnetClauseFactory.with_fabric_id(fabric_id),
                ]
            )
        )
        builder = subnet_request.to_builder(vlan_id=vlan_id)
        subnet = await services.subnets.update_one(
            query=query, builder=builder
        )

        response.headers["ETag"] = subnet.etag()
        return SubnetResponse.from_model(
            subnet=subnet, self_base_hyperlink=f"{V3_API_PREFIX}/subnets"
        )

    @handler(
        path="/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{id}",
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
    async def delete_fabric_vlan_subnet(
        self,
        fabric_id: int,
        vlan_id: int,
        id: int,
        etag_if_match: Union[str, None] = Header(
            alias="if-match", default=None
        ),
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        query = QuerySpec(
            where=SubnetClauseFactory.and_clauses(
                [
                    SubnetClauseFactory.with_id(id),
                    SubnetClauseFactory.with_vlan_id(vlan_id),
                    SubnetClauseFactory.with_fabric_id(fabric_id),
                ]
            )
        )
        await services.subnets.delete_one(
            query=query, etag_if_match=etag_if_match
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)


class UISubnetsHandler(Handler):
    """UI Subnets API handler."""

    TAGS = ["UI Subnets"]

    @handler(
        path="/subnets",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {"model": UISubnetsListResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_subnets(
        self,
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        filters: UISubnetFiltersParams = Depends(),  # noqa: B008
        order_by: UISubnetOrderByQueryFilter = Depends(),  # noqa: B008
        free_text_search: UISubnetsFreeTextSearchQueryParam = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> UISubnetsListResponse:
        filters_clause = filters.to_clause()
        free_text_search_clause = free_text_search.to_clause()
        where_clause = None
        if filters_clause and free_text_search_clause:
            where_clause = ClauseFactory.and_clauses(
                [filters_clause, free_text_search_clause]
            )
        elif filters_clause:
            where_clause = filters_clause
        elif free_text_search_clause:
            where_clause = free_text_search_clause

        query = QuerySpec(where=where_clause, order_by=order_by.to_clauses())
        subnets = await services.ui_subnets.list(
            page=pagination_params.page,
            size=pagination_params.size,
            query=query,
        )
        subnets.items = (
            await services.ui_subnets.calculate_statistics_for_subnets(
                subnets.items
            )
        )

        next_link = None
        if subnets.has_next(pagination_params.page, pagination_params.size):
            next_link = f"{V3_API_UI_PREFIX}/subnets?{pagination_params.to_next_href_format()}"
            if query_filters := filters.to_href_format():
                next_link += f"&{query_filters}"
            if free_text_search_filters := free_text_search.to_href_format():
                next_link += f"&{free_text_search_filters}"
            if order_by_filters := order_by.to_href_format():
                next_link += f"&{order_by_filters}"

        return UISubnetsListResponse(
            items=[
                UISubnetResponse.from_model(
                    subnet=subnet,
                    self_base_hyperlink=f"{V3_API_UI_PREFIX}/subnets",
                )
                for subnet in subnets.items
            ],
            total=subnets.total,
            next=next_link,
        )

    @handler(
        path="/subnets/{subnet_id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": UISubnetResponse,
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
    async def get_subnet(
        self,
        subnet_id: int,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> UISubnetResponse:
        subnet = await services.ui_subnets.get_by_id(subnet_id)
        if not subnet:
            raise NotFoundException()
        subnet = await services.ui_subnets.calculate_statistics_for_subnet(
            subnet
        )

        response.headers["ETag"] = subnet.etag()
        return UISubnetResponse.from_model(
            subnet=subnet,
            self_base_hyperlink=f"{V3_API_UI_PREFIX}/subnets",
        )
