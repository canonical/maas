#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Depends, Response

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    ValidationErrorBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.query import (
    TokenPaginationParams,
)
from maasapiserver.v3.api.public.models.responses.reservedips import (
    ReservedIPResponse,
    ReservedIPsListResponse,
)
from maasapiserver.v3.api.public.models.responses.resource_pools import (
    ResourcePoolsListResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.reservedips import (
    ReservedIPsClauseFactory,
)
from maasservicelayer.services import ServiceCollectionV3


class ReservedIPsHandler(Handler):
    """Reserved IPs API handler."""

    TAGS = ["ReservedIP"]

    @handler(
        path="/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/reserved_ips",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": ResourcePoolsListResponse,
            },
            422: {"model": ValidationErrorBodyResponse},
        },
        status_code=200,
        response_model_exclude_none=True,
        dependencies=[
            Depends(
                check_permissions(
                    required_roles={UserRole.USER},
                )
            )
        ],
    )
    async def list_fabric_vlan_subnet_reserved_ips(
        self,
        fabric_id: int,
        vlan_id: int,
        subnet_id: int,
        token_pagination_params: TokenPaginationParams = Depends(),
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        query = QuerySpec(
            where=ReservedIPsClauseFactory.and_clauses(
                [
                    ReservedIPsClauseFactory.with_fabric_id(fabric_id),
                    ReservedIPsClauseFactory.with_subnet_id(subnet_id),
                    ReservedIPsClauseFactory.with_vlan_id(vlan_id),
                ]
            )
        )
        reservedips = await services.reservedips.list(
            token=token_pagination_params.token,
            size=token_pagination_params.size,
            query=query,
        )
        return ReservedIPsListResponse(
            items=[
                ReservedIPResponse.from_model(
                    reservedip=reservedip,
                    self_base_hyperlink=f"{V3_API_PREFIX}/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/reserved_ips",
                )
                for reservedip in reservedips.items
            ],
            next=(
                f"{V3_API_PREFIX}/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/reserved_ips?"
                f"{TokenPaginationParams.to_href_format(reservedips.next_token, token_pagination_params.size)}"
                if reservedips.next_token
                else None
            ),
        )
