#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from fastapi import Depends, Path
from pydantic import BaseModel

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.v3.api import services
from maasservicelayer.builders.power_drivers import PowerDriverBuilder
from maasservicelayer.db.filters import ClauseFactory, QuerySpec
from maasservicelayer.db.repositories.power_drivers import (
    PowerDriverClauseFactory,
)
from maasservicelayer.services import ServiceCollectionV3


class DriverRegisterRequest(BaseModel):
    """Request body for driver registration.

    Accepts both snake_case (from Python) and camelCase (from Go agent).
    The Go agent serializes SocketDriver with JSON field tags that map to
    snake_case, so both forms are supported.
    """

    name: str
    version: str
    schema: dict[str, Any]


class DriverRegisterBody(BaseModel):
    """Request body containing multiple drivers to register."""

    drivers: list[DriverRegisterRequest]


class DriverListResponse(BaseModel):
    """Response body for listing registered drivers."""

    drivers: list[dict[str, Any]]


class RackPowerDriversHandler(Handler):
    """v3 internal API handler for rack power driver lifecycle."""

    @handler(
        path="/agents/{agent_uuid}/power-drivers:register",
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
        service_collection: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ):
        """Register one or more power drivers for a rack controller agent."""
        if body is None or not body.drivers:
            return

        builders = []
        for driver in body.drivers:
            builders.append(
                PowerDriverBuilder(
                    rack_system_id=agent_uuid,
                    driver_name=driver.name,
                    driver_version=driver.version,
                    schema=driver.schema,
                )
            )

        await service_collection.power_drivers.upsert_many(builders)

    @handler(
        path="/agents/{agent_uuid}/power-drivers/{driver_name}/{version}",
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
        service_collection: ServiceCollectionV3 = Depends(services),  # noqa: B008
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
        await service_collection.power_drivers.delete_one(query)

    @handler(
        path="/agents/{agent_uuid}/power-drivers",
        methods=["GET"],
        responses={
            200: {"model": DriverListResponse},
        },
        status_code=200,
    )
    async def list_drivers(
        self,
        agent_uuid: str = Path(),
        service_collection: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ):
        """List all registered power drivers for a rack controller agent."""
        query = QuerySpec(
            where=PowerDriverClauseFactory.with_rack_system_id(agent_uuid)
        )
        drivers = await service_collection.power_drivers.get_many(query)

        driver_list = []
        for driver in drivers:
            driver_list.append(
                {
                    "name": driver.driver_name,
                    "version": driver.driver_version,
                    "schema": driver.schema,
                }
            )

        return DriverListResponse(drivers=driver_list)
