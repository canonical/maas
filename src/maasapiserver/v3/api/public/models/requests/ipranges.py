# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv6Address
from typing import cast

from netaddr import IPAddress
from pydantic import BaseModel, Field, IPvAnyAddress, model_validator

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
from maasservicelayer.models.ipranges import IPRange as IPRangeModel
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
    comment: str | None = Field(
        description="A description of this range.", default=None
    )
    owner_id: int | None = Field(
        description="The owner of this range.", default=None
    )

    @model_validator(mode="after")
    def validate_ip_addresses(self) -> "IPRangeCreateRequest":
        if self.start_ip.version != self.end_ip.version:
            raise ValidationException.build_for_field(
                "start_ip",
                "Start IP address and end IP address must be in the same address family.",
            )
        if self.end_ip < self.start_ip:  # pyright: ignore[reportOperatorIssue]
            raise ValidationException.build_for_field(
                "end_ip",
                "End IP address must not be less than Start IP address.",
            )
        return self

    def _validate_addresses_in_subnet(self, subnet: Subnet):
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
            and (self.start_ip + 255) > cast(IPv6Address, self.end_ip)  # pyright: ignore[reportOperatorIssue]
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
        existing_iprange: IPRangeModel | None = None,
    ) -> IPRangeBuilder:
        self._validate_addresses_in_subnet(subnet)
        if self.type == IPRangeType.DYNAMIC:
            if not (
                await services.openfga_tuples.get_client().can_edit_global_entities(
                    authenticated_user.id
                )
            ):
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

        start_ip = IPAddress(str(self.start_ip))
        end_ip = IPAddress(str(self.end_ip))

        found = any(
            start_ip in unused_range and end_ip in unused_range
            for unused_range in unused
        )

        if not found and not self._is_existing_dynamic_range_resize_allowed(
            start_ip, end_ip, unused, existing_iprange
        ):
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

    def _is_existing_dynamic_range_resize_allowed(
        self,
        start_ip: IPAddress,
        end_ip: IPAddress,
        unused,
        existing_iprange: IPRangeModel | None,
    ) -> bool:
        """Allow resizing a dynamic range despite existing in-range allocations."""
        if (
            self.type != IPRangeType.DYNAMIC
            or existing_iprange is None
            or existing_iprange.type != IPRangeType.DYNAMIC
        ):
            return False

        existing_start = int(IPAddress(str(existing_iprange.start_ip)))
        existing_end = int(IPAddress(str(existing_iprange.end_ip)))
        start = int(start_ip)
        end = int(end_ip)

        added_segments = []

        left_end = min(end, existing_start - 1)
        if start <= left_end:
            added_segments.append((start, left_end))

        right_start = max(start, existing_end + 1)
        if right_start <= end:
            added_segments.append((right_start, end))

        if not added_segments:
            return True

        version = start_ip.version
        for segment_start, segment_end in added_segments:
            added_start_ip = IPAddress(segment_start, version=version)
            added_end_ip = IPAddress(segment_end, version=version)
            if not any(
                added_start_ip in unused_range and added_end_ip in unused_range
                for unused_range in unused
            ):
                return False

        return True


class IPRangeUpdateRequest(IPRangeCreateRequest):
    owner_id: int = Field(description="The owner of this range.")  # type: ignore
