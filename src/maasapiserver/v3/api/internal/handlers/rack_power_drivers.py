#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Depends, Path

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.v3.api import services
from maasapiserver.v3.api.internal.models.requests.power_drivers import (
    DriverRegisterBody,
)
from maasservicelayer.builders.power_drivers import PowerDriverBuilder
from maasservicelayer.db.filters import ClauseFactory, QuerySpec
from maasservicelayer.db.repositories.power_drivers import (
    PowerDriverClauseFactory,
)
from maasservicelayer.services import ServiceCollectionV3


class RackPowerDriversHandler(Handler):
    """v3 internal API handler for rack power driver lifecycle."""

    @handler(
        path="/agents/{agent_uuid}/power-driver:register",
        methods=["POST"],
        responses={
            204: {},
        },
        status_code=204,
    )
    async def register_drivers(
        self,
        agent_uuid: str = Path(),
        body: DriverRegisterBody | None = None,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ):
        """Register one or more power drivers for a rack controller agent."""
        if body is None or not body.drivers:
            return

        builders = [
            PowerDriverBuilder(
                rack_system_id=agent_uuid,
                driver_name=driver.name,
                driver_version=driver.version,
                schema=driver.schema,
            )
            for driver in body.drivers
        ]

        await services.power_drivers.upsert_many(builders)

    @handler(
        path="/agents/{agent_uuid}/power-driver/{driver_name}/{version}",
        methods=["DELETE"],
        responses={
            204: {},
        },
        status_code=204,
    )
    async def unregister_driver(
        self,
        agent_uuid: str = Path(),
        driver_name: str = Path(),
        version: str = Path(),
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ):
        """Unregister a specific version of a power driver."""
        query = QuerySpec(
            where=ClauseFactory.and_clauses(
                [
                    PowerDriverClauseFactory.with_rack_system_id(agent_uuid),
                    PowerDriverClauseFactory.with_driver_name(driver_name),
                    PowerDriverClauseFactory.with_driver_version(version),
                ]
            )
        )
        await services.power_drivers.delete_one(query)
