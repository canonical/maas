# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Union

from fastapi import Depends, Header, Response, status

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    NotFoundBodyResponse,
    NotFoundResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.ipranges import (
    IPRangeCreateRequest,
    IPRangeUpdateRequest,
)
from maasapiserver.v3.api.public.models.requests.query import PaginationParams
from maasapiserver.v3.api.public.models.responses.base import (
    OPENAPI_ETAG_HEADER,
)
from maasapiserver.v3.api.public.models.responses.ipranges import (
    IPRangeListResponse,
    IPRangeResponse,
)
from maasapiserver.v3.auth.base import (
    check_permissions,
    get_authenticated_user,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.ipranges import IPRangeClauseFactory
from maasservicelayer.db.repositories.subnets import SubnetClauseFactory
from maasservicelayer.exceptions.catalog import (
    BadRequestException,
    BaseExceptionDetail,
    ForbiddenException,
    NotFoundException,
)
from maasservicelayer.exceptions.constants import (
    INVALID_ARGUMENT_VIOLATION_TYPE,
    MISSING_PERMISSIONS_VIOLATION_TYPE,
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
)
from maasservicelayer.models.auth import AuthenticatedUser
from maasservicelayer.services import ServiceCollectionV3


class IPRangesHandler(Handler):
    """IPRanges API handler."""

    TAGS = ["IPRanges"]

    @handler(
        path="/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/ipranges",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": IPRangeListResponse,
            },
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_fabric_vlan_subnet_iprange(
        self,
        fabric_id: int,
        vlan_id: int,
        subnet_id: int,
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> IPRangeListResponse:
        ipranges = await services.ipranges.list(
            page=pagination_params.page,
            size=pagination_params.size,
            query=QuerySpec(
                where=IPRangeClauseFactory.and_clauses(
                    [
                        IPRangeClauseFactory.with_subnet_id(subnet_id),
                        IPRangeClauseFactory.with_vlan_id(vlan_id),
                        IPRangeClauseFactory.with_fabric_id(fabric_id),
                    ]
                )
            ),
        )
        return IPRangeListResponse(
            items=[
                IPRangeResponse.from_model(
                    iprange=iprange,
                    self_base_hyperlink=f"{V3_API_PREFIX}/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/ipranges/",
                )
                for iprange in ipranges.items
            ],
            total=ipranges.total,
            next=(
                f"{V3_API_PREFIX}/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/ipranges?"
                f"{pagination_params.to_next_href_format()}"
                if ipranges.has_next(
                    pagination_params.page, pagination_params.size
                )
                else None
            ),
        )

    @handler(
        path="/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/ipranges",
        methods=["POST"],
        tags=TAGS,
        responses={
            201: {
                "model": IPRangeResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=201,
        dependencies=[
            # Additional permission checks are performed in the builder.
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def create_fabric_vlan_subnet_iprange(
        self,
        fabric_id: int,
        vlan_id: int,
        subnet_id: int,
        iprange_request: IPRangeCreateRequest,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
        authenticated_user: AuthenticatedUser = Depends(  # noqa: B008
            get_authenticated_user
        ),
    ) -> Response:
        if (
            not authenticated_user.is_admin()
            and iprange_request.owner_id is not None
            and iprange_request.owner_id != authenticated_user.id
        ):
            raise BadRequestException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_ARGUMENT_VIOLATION_TYPE,
                        message="Only admins can create IP ranges on behalf of other users.",
                    )
                ]
            )

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
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                        message=f"Could not find subnet {subnet_id} in VLAN {vlan_id} in fabric {fabric_id}.",
                    )
                ]
            )
        builder = await iprange_request.to_builder(
            subnet, authenticated_user, services
        )
        iprange = await services.ipranges.create(builder)

        response.headers["ETag"] = iprange.etag()
        return IPRangeResponse.from_model(
            iprange=iprange,
            self_base_hyperlink=f"{V3_API_PREFIX}/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/ipranges/",
        )

    @handler(
        path="/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/ipranges/{id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": IPRangeResponse,
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
    async def get_fabric_vlan_subnet_iprange(
        self,
        fabric_id: int,
        vlan_id: int,
        subnet_id: int,
        id: int,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        iprange = await services.ipranges.get_one(
            QuerySpec(
                where=IPRangeClauseFactory.and_clauses(
                    [
                        IPRangeClauseFactory.with_id(id),
                        IPRangeClauseFactory.with_subnet_id(subnet_id),
                        IPRangeClauseFactory.with_vlan_id(vlan_id),
                        IPRangeClauseFactory.with_fabric_id(fabric_id),
                    ]
                )
            )
        )
        if not iprange:
            return NotFoundResponse()

        response.headers["ETag"] = iprange.etag()
        return IPRangeResponse.from_model(
            iprange=iprange,
            self_base_hyperlink=f"{V3_API_PREFIX}/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/ipranges/",
        )

    @handler(
        path="/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/ipranges/{iprange_id}",
        methods=["DELETE"],
        tags=TAGS,
        responses={
            204: {},
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=204,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def delete_fabric_vlan_subnet_iprange(
        self,
        fabric_id: int,
        vlan_id: int,
        subnet_id: int,
        iprange_id: int,
        etag_if_match: Union[str, None] = Header(
            alias="if-match", default=None
        ),
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
        authenticated_user: AuthenticatedUser = Depends(  # noqa: B008
            get_authenticated_user
        ),
    ) -> Response:
        iprange = await services.ipranges.get_one(
            query=QuerySpec(
                where=IPRangeClauseFactory.and_clauses(
                    [
                        IPRangeClauseFactory.with_id(iprange_id),
                        IPRangeClauseFactory.with_subnet_id(subnet_id),
                        IPRangeClauseFactory.with_vlan_id(vlan_id),
                        IPRangeClauseFactory.with_fabric_id(fabric_id),
                    ]
                )
            )
        )
        if iprange:
            if (
                iprange.user_id != authenticated_user.id
                and not authenticated_user.is_admin()
            ):
                raise ForbiddenException(
                    details=[
                        BaseExceptionDetail(
                            type=MISSING_PERMISSIONS_VIOLATION_TYPE,
                            message="Only the owner of the iprange or an admin can delete the iprange.",
                        )
                    ]
                )
            await services.ipranges.delete_by_id(
                iprange.id, etag_if_match=etag_if_match
            )

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @handler(
        path="/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/ipranges/{iprange_id}",
        methods=["PUT"],
        tags=TAGS,
        responses={
            200: {
                "model": IPRangeResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            # Additional permission checks are performed in the builder.
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def update_fabric_vlan_subnet_iprange(
        self,
        fabric_id: int,
        vlan_id: int,
        subnet_id: int,
        iprange_id: int,
        iprange_request: IPRangeUpdateRequest,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
        authenticated_user: AuthenticatedUser = Depends(  # noqa: B008
            get_authenticated_user
        ),
    ) -> Response:
        if (
            not authenticated_user.is_admin()
            and iprange_request.owner_id != authenticated_user.id
        ):
            raise BadRequestException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_ARGUMENT_VIOLATION_TYPE,
                        message="Only admins can update IP ranges for other users.",
                    )
                ]
            )
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
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                        message=f"Could not find subnet {subnet_id} in VLAN {vlan_id} in fabric {fabric_id}.",
                    )
                ]
            )
        iprange = await services.ipranges.get_one(
            query=QuerySpec(
                where=IPRangeClauseFactory.and_clauses(
                    [
                        IPRangeClauseFactory.with_id(iprange_id),
                        IPRangeClauseFactory.with_subnet_id(subnet_id),
                    ]
                )
            )
        )
        if not iprange:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                        message=f"Could not find IP range {iprange_id} in subnet {subnet_id} in VLAN {vlan_id} in fabric {fabric_id}.",
                    )
                ]
            )

        # the user is trying to modify an iprange that doesn't belong to him.
        if (
            not authenticated_user.is_admin()
            and iprange.user_id != authenticated_user.id
        ):
            raise ForbiddenException(
                details=[
                    BaseExceptionDetail(
                        type=MISSING_PERMISSIONS_VIOLATION_TYPE,
                        message="Only admins can update IP ranges for other users.",
                    )
                ]
            )

        builder = await iprange_request.to_builder(
            subnet, authenticated_user, services, iprange.id
        )
        iprange = await services.ipranges.update_one(
            query=QuerySpec(
                where=IPRangeClauseFactory.and_clauses(
                    [
                        IPRangeClauseFactory.with_id(iprange_id),
                        IPRangeClauseFactory.with_subnet_id(subnet_id),
                    ]
                )
            ),
            builder=builder,
        )

        response.headers["ETag"] = iprange.etag()
        return IPRangeResponse.from_model(
            iprange=iprange,
            self_base_hyperlink=f"{V3_API_PREFIX}/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/ipranges/",
        )
