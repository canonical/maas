#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Depends

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.responses.power_types import (
    PowerTypeField,
    PowerTypeResponse,
    PowerTypesListResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.services import ServiceCollectionV3


class PowerTypesHandler(Handler):
    """Power types API handler with FIPS annotations."""

    TAGS = ["Power Types"]

    @handler(
        path="/power-types",
        methods=["GET"],
        tags=TAGS,
        responses={200: {"model": PowerTypesListResponse}},
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_power_types(
        self,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> PowerTypesListResponse:
        power_types = await services.power_types.list()
        return PowerTypesListResponse(
            items=[
                PowerTypeResponse(
                    driver_type=pt.get("driver_type", "power"),
                    name=pt["name"],
                    description=pt["description"],
                    fields=[
                        PowerTypeField(
                            name=f["name"],
                            label=f["label"],
                            required=f["required"],
                            field_type=f["field_type"],
                            default=f.get("default"),
                            choices=f.get("choices"),
                        )
                        for f in pt.get("fields", [])
                    ],
                    chassis=pt["chassis"],
                    can_probe=pt["can_probe"],
                    missing_packages=pt["missing_packages"],
                    queryable=pt.get("queryable", False),
                    fips_supported=pt["fips_supported"],
                    fips_unsupported_reason=pt.get("fips_unsupported_reason"),
                )
                for pt in power_types
            ]
        )
