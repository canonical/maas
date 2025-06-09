# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import BaseModel, conint, Field, IPvAnyAddress

from maasservicelayer.builders.staticroutes import StaticRouteBuilder
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.subnets import SubnetClauseFactory
from maasservicelayer.exceptions.catalog import ValidationException
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services import ServiceCollectionV3

StrictNonNegativeInt = conint(strict=True, ge=0)


class StaticRouteRequest(BaseModel):
    gateway_ip: IPvAnyAddress = Field(
        description="IP address of the gateway on the source subnet."
    )
    destination_id: int = Field(
        description="Destination subnet ID for the route."
    )
    metric: StrictNonNegativeInt = Field(  # pyright: ignore [reportInvalidTypeForm]
        description="Weight of the route on a deployed machine.", default=0
    )

    async def to_builder(
        self, source_subnet: Subnet, services: ServiceCollectionV3
    ) -> StaticRouteBuilder:
        destination_subnet = await services.subnets.get_one(
            query=QuerySpec(
                where=SubnetClauseFactory.with_id(self.destination_id)
            )
        )
        if not destination_subnet:
            raise ValidationException.build_for_field(
                "destination_id",
                f"The destination subnet with id '{self.destination_id}' does not exist.",
            )

        if source_subnet.cidr.version != destination_subnet.cidr.version:
            raise ValidationException.build_for_field(
                "destination_id",
                "source and destination subnets must have be the same IP version.",
            )
        if self.gateway_ip not in source_subnet.cidr:
            raise ValidationException.build_for_field(
                "gateway_ip",
                f"gateway_ip must be with in the source subnet {source_subnet.cidr}.",
            )
        return StaticRouteBuilder(
            gateway_ip=self.gateway_ip,
            source_id=source_subnet.id,
            destination_id=destination_subnet.id,
            metric=self.metric,
        )
