# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import BaseModel, Field, IPvAnyAddress

from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.reservedips import (
    ReservedIPsResourceBuilder,
)
from maasservicelayer.db.repositories.staticipaddress import (
    StaticIPAddressClauseFactory,
)
from maasservicelayer.exceptions.catalog import ValidationException
from maasservicelayer.models.fields import MacAddress
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.utils.date import utcnow


class ReservedIPCreateRequest(BaseModel):
    ip: IPvAnyAddress = Field(description="The IP to be reserved.")
    mac_address: MacAddress = Field(
        description="The MAC address that should be linked to the reserved IP."
    )
    comment: str | None = Field(
        description="A description of this reserved IP.", default=None
    )

    async def to_builder(
        self, subnet: Subnet, services: ServiceCollectionV3
    ) -> ReservedIPsResourceBuilder:
        existing_ip = await services.staticipaddress.get_one(
            QuerySpec(where=StaticIPAddressClauseFactory.with_ip(self.ip))
        )
        if existing_ip is not None:
            mac_addresses = await services.staticipaddress.get_mac_addresses(
                query=QuerySpec(
                    where=StaticIPAddressClauseFactory.with_id(existing_ip.id)
                )
            )
            if self.mac_address not in mac_addresses:
                raise ValidationException.build_for_field(
                    "ip",
                    f"The ip {self.ip} is already in use by another machine.",
                )

        dynamic_range = await services.ipranges.get_dynamic_range_for_ip(
            subnet.id, self.ip
        )
        if dynamic_range is not None:
            raise ValidationException.build_for_field(
                "ip",
                f"The ip {self.ip} must be outside the dynamic range {dynamic_range.start_ip} - {dynamic_range.end_ip}.",
            )
        if self.ip not in subnet.cidr:
            raise ValidationException.build_for_field(
                "ip", "The provided ip is not part of the subnet."
            )
        if self.ip == subnet.cidr.network_address:
            raise ValidationException.build_for_field(
                "ip", "The network address cannot be a reserved IP."
            )
        if self.ip == subnet.cidr.broadcast_address:
            raise ValidationException.build_for_field(
                "ip", "The broadcast address cannot be a reserved IP."
            )
        now = utcnow()
        builder = (
            ReservedIPsResourceBuilder()
            .with_ip(self.ip)
            .with_mac_address(self.mac_address)
            .with_subnet_id(subnet.id)
            .with_comment(self.comment)
            .with_created(now)
            .with_updated(now)
        )
        return builder
