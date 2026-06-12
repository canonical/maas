# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Depends

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    NotFoundBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.operations import (
    OperationFilterParams,
)
from maasapiserver.v3.api.public.models.requests.query import PaginationParams
from maasapiserver.v3.api.public.models.responses.operations import (
    OperationResponse,
    OperationsListResponse,
)
from maasapiserver.v3.auth.base import (
    check_authentication,
    get_authenticated_user,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    NotFoundException,
)
from maasservicelayer.models.auth import AuthenticatedUser
from maasservicelayer.services import ServiceCollectionV3


class OperationsHandler(Handler):
    """Operations API handler."""

    TAGS = ["Operations"]

    @handler(
        path="/operations",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": OperationsListResponse,
            },
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[Depends(check_authentication())],
    )
    async def list_operations(
        self,
        filters: OperationFilterParams = Depends(),  # noqa: B008
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        authenticated_user: AuthenticatedUser | None = Depends(  # noqa: B008
            get_authenticated_user
        ),
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> OperationsListResponse:
        """List all operations with pagination and filtering."""

        assert authenticated_user is not None
        can_view_all = (
            await services.openfga_tuples.get_client().can_view_operations(
                authenticated_user.id
            )
        )
        filter_clause = filters.to_clause()

        operations = await services.operations.list_for_user(
            pagination_params.page,
            pagination_params.size,
            user_id=authenticated_user.id,
            can_view_all=can_view_all,
            query=QuerySpec(where=filter_clause),
        )

        next_link = None
        if operations.has_next(pagination_params.page, pagination_params.size):
            next_link = (
                f"{V3_API_PREFIX}/operations?"
                f"{pagination_params.to_next_href_format()}"
            )
            if query_filters := filters.to_href_format():
                next_link += f"&{query_filters}"

        return OperationsListResponse(
            items=[
                OperationResponse.from_model(
                    operation=operation,
                    self_base_hyperlink=f"{V3_API_PREFIX}/operations",
                )
                for operation in operations.items
            ],
            total=operations.total,
            next=next_link,
        )

    @handler(
        path="/operations/{operation_uuid}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": OperationResponse,
            },
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[Depends(check_authentication())],
    )
    async def get_operation(
        self,
        operation_uuid: str,
        authenticated_user: AuthenticatedUser | None = Depends(  # noqa: B008
            get_authenticated_user
        ),
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> OperationResponse:
        """Get a specific operation by UUID."""

        assert authenticated_user is not None
        can_view_all = (
            await services.openfga_tuples.get_client().can_view_operations(
                authenticated_user.id
            )
        )
        operation = await services.operations.get_by_uuid_for_user(
            operation_uuid,
            user_id=authenticated_user.id,
            can_view_all=can_view_all,
        )
        if not operation:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type="OperationNotFound",
                        message=f"Operation with uuid '{operation_uuid}' was not found.",
                    )
                ]
            )

        return OperationResponse.from_model(
            operation=operation,
            self_base_hyperlink=f"{V3_API_PREFIX}/operations",
        )
