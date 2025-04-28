# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from netaddr import IPAddress
from pydantic import BaseModel, Field, IPvAnyAddress

from maascommon.enums.ipranges import IPRangeType
from maasservicelayer.builders.ipranges import IPRangeBuilder
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    ConflictException,
    ForbiddenException,
    ValidationException,
)
from maasservicelayer.exceptions.constants import (
    CONFLICT_VIOLATION_TYPE,
    INVALID_ARGUMENT_VIOLATION_TYPE,
    MISSING_PERMISSIONS_VIOLATION_TYPE,
)
from maasservicelayer.models.auth import AuthenticatedUser
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services import ServiceCollectionV3


class IPRangeCreateRequest(BaseModel):
    type: IPRangeType = Field(description="Type of this range.")
    start_ip: IPvAnyAddress = Field(
        description="Start IP address of this range (inclusive)."
    )
    end_ip: IPvAnyAddress = Field(
        description="Last IP address of this range (inclusive)."
    )
    comment: Optional[str] = Field(
        description="A description of this range.", default=None
    )
    owner_id: Optional[int] = Field(
        description="The owner of this range.", default=None
    )

    def _validate_addresses_in_subnet(self, subnet: Subnet):
        if self.start_ip.version != self.end_ip.version:
            raise ValidationException.build_for_field(
                "start_ip",
                "Start IP address and end IP address must be in the same address family.",
            )
        if self.end_ip < self.start_ip:
            raise ValidationException.build_for_field(
                "end_ip",
                "End IP address must not be less than Start IP address.",
            )

        if self.start_ip not in subnet.cidr:
            raise ValidationException.build_for_field(
                "start_ip",
                f"Start IP address must be within subnet: {subnet.cidr}.",
            )
        if self.end_ip not in subnet.cidr:
            raise ValidationException.build_for_field(
                "end_ip",
                f"End IP address must be within subnet: {subnet.cidr}.",
            )
        if subnet.cidr.network_address == self.start_ip:
            raise ValidationException.build_for_field(
                "start_ip",
                "Reserved network address cannot be included in IP range.",
            )
        if (
            subnet.cidr.version == 4
            and subnet.cidr.broadcast_address == self.end_ip
        ):
            raise ValidationException.build_for_field(
                "end_ip",
                "Broadcast address cannot be included in IP range.",
            )
        if (
            self.start_ip.version == 6
            and self.type == IPRangeType.DYNAMIC
            and (self.start_ip + 255) > self.end_ip
        ):
            raise ValidationException.build_for_field(
                "start_ip",
                "IPv6 dynamic range must be at least 256 addresses in size.",
            )

    async def to_builder(
        self,
        subnet: Subnet,
        authenticated_user: AuthenticatedUser,
        services: ServiceCollectionV3,
        existing_iprange_id: int | None = None,
    ) -> IPRangeBuilder:
        self._validate_addresses_in_subnet(subnet)
        if self.type == IPRangeType.DYNAMIC:
            if not authenticated_user.is_admin():
                raise ForbiddenException(
                    details=[
                        BaseExceptionDetail(
                            type=MISSING_PERMISSIONS_VIOLATION_TYPE,
                            message="Only admins can create/update dynamic IP ranges.",
                        )
                    ]
                )
            has_reserved_ips = (
                await services.reservedips.exists_within_subnet_iprange(
                    subnet_id=subnet.id,
                    start_ip=self.start_ip,
                    end_ip=self.end_ip,
                )
            )
            if has_reserved_ips:
                raise ValidationException(
                    details=[
                        BaseExceptionDetail(
                            type=INVALID_ARGUMENT_VIOLATION_TYPE,
                            message="The dynamic IP range would include some IPs that are already reserved. Remove them first.",
                        )
                    ]
                )
            # Dynamic ranges cannot overlap anything (no ranges or IPs).
            unused = await services.v3subnet_utilization.get_ipranges_available_for_dynamic_range(
                subnet_id=subnet.id, exclude_ip_range_id=existing_iprange_id
            )
        else:
            # Reserved ranges can overlap allocated IPs but not other ranges.
            unused = await services.v3subnet_utilization.get_ipranges_available_for_reserved_range(
                subnet_id=subnet.id, exclude_ip_range_id=existing_iprange_id
            )
        if not unused:
            raise ValidationException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_ARGUMENT_VIOLATION_TYPE,
                        message=f"There is no room for any {self.type} ranges on this subnet.",
                    )
                ]
            )

        found = False
        # Find unused range for start_ip
        for unused_range in unused:
            if IPAddress(str(self.start_ip)) in unused_range:
                if IPAddress(str(self.end_ip)) in unused_range:
                    # Success, start and end IP are in an unused range.
                    found = True
                    break

        if not found:
            message = (
                f"Requested {self.type} range conflicts with an existing "
            )
            if self.type == IPRangeType.RESERVED:
                message += "range."
            else:
                message += "IP address or range."
            raise ConflictException(
                details=[
                    BaseExceptionDetail(
                        type=CONFLICT_VIOLATION_TYPE,
                        message=message,
                    )
                ]
            )

        return IPRangeBuilder(
            type=self.type,
            start_ip=self.start_ip,
            end_ip=self.end_ip,
            comment=self.comment,
            subnet_id=subnet.id,
            user_id=(
                self.owner_id
                if self.owner_id is not None
                else authenticated_user.id
            ),
        )


class IPRangeUpdateRequest(IPRangeCreateRequest):
    owner_id: int = Field(description="The owner of this range.")  # type: ignore
