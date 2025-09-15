# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
from typing import Annotated, Optional, Union

from fastapi import Depends, Header, Query, Response
from starlette import status

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    NotFoundBodyResponse,
    PreconditionFailedBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.query import PaginationParams
from maasapiserver.v3.api.public.models.responses.base import (
    OPENAPI_ETAG_HEADER,
)
from maasapiserver.v3.api.public.models.responses.boot_resources import (
    BootResourceListResponse,
    BootResourceResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.boot_resources import (
    BootResourceStrType,
    BootResourceType,
)
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootresources import (
    BootResourceClauseFactory,
)
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.services import ServiceCollectionV3

TYPE_MAPPING = {
    BootResourceStrType.SYNCED: BootResourceType.SYNCED,
    BootResourceStrType.UPLOADED: BootResourceType.UPLOADED,
}


class BootResourcesHandler(Handler):
    """BootResources API handler."""

    TAGS = ["BootResources"]

    @handler(
        path="/boot_resources",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": BootResourceListResponse,
            },
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_boot_resources(
        self,
        type: Annotated[
            Optional[BootResourceStrType],
            Query(description="Filter boot resources of a particular type"),
        ] = None,
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> BootResourceListResponse:
        query_spec = QuerySpec()
        if type:
            query_spec = QuerySpec(
                where=BootResourceClauseFactory.with_rtype(TYPE_MAPPING[type]),
            )
        boot_resources = await services.boot_resources.list(
            page=pagination_params.page,
            size=pagination_params.size,
            query=query_spec,
        )
        return BootResourceListResponse(
            items=[
                BootResourceResponse.from_model(
                    boot_resource=boot_resource,
                    self_base_hyperlink=f"{V3_API_PREFIX}/boot_resources",
                )
                for boot_resource in boot_resources.items
            ],
            total=boot_resources.total,
            next=(
                f"{V3_API_PREFIX}/boot_resources?"
                f"{pagination_params.to_next_href_format()}"
                if boot_resources.has_next(
                    pagination_params.page, pagination_params.size
                )
                else None
            ),
        )

    @handler(
        path="/boot_resources/{id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": BootResourceResponse,
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
    async def get_boot_resource_by_id(
        self,
        id: int,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> BootResourceResponse:
        boot_resource = await services.boot_resources.get_by_id(id=id)
        if boot_resource is None:
            raise NotFoundException()
        response.headers["ETag"] = boot_resource.etag()
        return BootResourceResponse.from_model(
            boot_resource=boot_resource,
            self_base_hyperlink=f"{V3_API_PREFIX}/boot_resources",
        )

    @handler(
        path="/boot_resources/{resource_id}",
        methods=["DELETE"],
        tags=TAGS,
        responses={
            204: {},
            404: {"model": NotFoundBodyResponse},
            412: {"model": PreconditionFailedBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=204,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def delete_boot_resource_by_id(
        self,
        resource_id: int,
        etag_if_match: Union[str, None] = Header(
            alias="if-match", default=None
        ),
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        await services.boot_resources.delete_by_id(
            id=resource_id,
            etag_if_match=etag_if_match,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
