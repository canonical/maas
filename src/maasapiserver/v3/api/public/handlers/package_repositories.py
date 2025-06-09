# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Union

from fastapi import Depends, Header, Response, status

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    BadRequestBodyResponse,
    ConflictBodyResponse,
    NotFoundBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.package_repositories import (
    PackageRepositoryCreateRequest,
    PackageRepositoryUpdateRequest,
)
from maasapiserver.v3.api.public.models.requests.query import PaginationParams
from maasapiserver.v3.api.public.models.responses.base import (
    OPENAPI_ETAG_HEADER,
)
from maasapiserver.v3.api.public.models.responses.package_repositories import (
    PackageRepositoryListResponse,
    PackageRepositoryResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.services import ServiceCollectionV3


class PackageRepositoriesHandler(Handler):
    """Package repositories handler."""

    TAGS = ["Package repositories"]

    @handler(
        path="/package_repositories",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": PackageRepositoryListResponse,
            },
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_package_repositories(
        self,
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> PackageRepositoryListResponse:
        package_repositories = await services.package_repositories.list(
            page=pagination_params.page,
            size=pagination_params.size,
        )
        next_link = None
        if package_repositories.has_next(
            pagination_params.page, pagination_params.size
        ):
            next_link = f"{V3_API_PREFIX}/package_repositories?{pagination_params.to_next_href_format()}"

        return PackageRepositoryListResponse(
            items=[
                PackageRepositoryResponse.from_model(
                    package_repository=package_repository,
                    self_base_hyperlink=f"{V3_API_PREFIX}/package_repositories",
                )
                for package_repository in package_repositories.items
            ],
            total=package_repositories.total,
            next=next_link,
        )

    @handler(
        path="/package_repositories",
        methods=["POST"],
        tags=TAGS,
        responses={
            201: {
                "model": PackageRepositoryResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            409: {"model": ConflictBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=201,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def create_package_repository(
        self,
        response: Response,
        package_repository_request: PackageRepositoryCreateRequest,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> PackageRepositoryResponse:
        package_repository = await services.package_repositories.create(
            package_repository_request.to_builder()
        )
        response.headers["ETag"] = package_repository.etag()
        return PackageRepositoryResponse.from_model(
            package_repository=package_repository,
            self_base_hyperlink=f"{V3_API_PREFIX}/package_repositories",
        )

    @handler(
        path="/package_repositories/{package_repository_id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": PackageRepositoryResponse,
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
    async def get_package_repository(
        self,
        package_repository_id: int,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> PackageRepositoryResponse:
        package_repository = await services.package_repositories.get_by_id(
            package_repository_id
        )
        if not package_repository:
            raise NotFoundException()

        response.headers["ETag"] = package_repository.etag()
        return PackageRepositoryResponse.from_model(
            package_repository=package_repository,
            self_base_hyperlink=f"{V3_API_PREFIX}/package_repositories",
        )

    @handler(
        path="/package_repositories/{package_repository_id}",
        methods=["PUT"],
        tags=TAGS,
        responses={
            200: {
                "model": PackageRepositoryResponse,
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
    async def update_package_repository(
        self,
        package_repository_id: int,
        package_repository_request: PackageRepositoryUpdateRequest,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> PackageRepositoryResponse:
        package_repository = await services.package_repositories.get_by_id(
            package_repository_id
        )

        if not package_repository:
            raise NotFoundException()

        builder = package_repository_request.to_builder(
            is_default=package_repository.default
        )
        package_repository = await services.package_repositories.update_by_id(
            package_repository_id, builder
        )

        response.headers["ETag"] = package_repository.etag()
        return PackageRepositoryResponse.from_model(
            package_repository=package_repository,
            self_base_hyperlink=f"{V3_API_PREFIX}/package_repositories",
        )

    @handler(
        path="/package_repositories/{package_repository_id}",
        methods=["DELETE"],
        tags=TAGS,
        responses={
            204: {},
            400: {"model": BadRequestBodyResponse},
            404: {"model": NotFoundBodyResponse},
        },
        status_code=204,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def delete_package_repository(
        self,
        package_repository_id: int,
        etag_if_match: Union[str, None] = Header(
            alias="if-match", default=None
        ),
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        await services.package_repositories.delete_by_id(
            package_repository_id, etag_if_match
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
