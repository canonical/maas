from fastapi import Depends, Response

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    ValidationErrorBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.models.requests.query import PaginationParams
from maasapiserver.v3.api.models.responses.machines import MachinesListResponse
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.auth.jwt import UserRole
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.services import ServiceCollectionV3


class MachinesHandler(Handler):
    """Machines API handler."""

    TAGS = ["Machines"]

    @handler(
        path="/machines",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": MachinesListResponse,
            },
            422: {"model": ValidationErrorBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_machines(
        self,
        pagination_params: PaginationParams = Depends(),
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        machines = await services.machines.list(pagination_params)
        return MachinesListResponse(
            items=[
                machine.to_response(f"{V3_API_PREFIX}/machines")
                for machine in machines.items
            ],
            total=machines.total,
        )
