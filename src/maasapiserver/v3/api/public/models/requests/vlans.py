# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from pydantic import Field

from maasapiserver.v3.api.public.models.requests.base import (
    OptionalNamedBaseModel,
)
from maascommon.enums.node import NodeTypeEnum
from maascommon.enums.service import ServiceName, ServiceStatusEnum
from maasservicelayer.builders.vlans import VlanBuilder
from maasservicelayer.db.filters import ClauseFactory, QuerySpec
from maasservicelayer.db.repositories.ipranges import IPRangeClauseFactory
from maasservicelayer.db.repositories.nodes import NodeClauseFactory
from maasservicelayer.db.repositories.service_status import (
    ServiceStatusClauseFactory,
)
from maasservicelayer.db.repositories.subnets import SubnetClauseFactory
from maasservicelayer.db.repositories.vlans import VlansClauseFactory
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    ValidationException,
)
from maasservicelayer.exceptions.constants import (
    MISSING_DYNAMIC_RANGE_VIOLATION_TYPE,
)
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.vlans import DEFAULT_MTU, DEFAULT_VID


class VlanCreateRequest(OptionalNamedBaseModel):
    description: str = Field(
        description="The description of the VLAN.", default=""
    )
    vid: int = Field(
        description="The VLAN ID of the VLAN. Valid values are within the range [0, 4094].",
        default=DEFAULT_VID,
        ge=0,
        le=4094,
    )
    # Linux doesn't allow lower than 552 for the MTU.
    mtu: int = Field(
        description="The MTU to use on the VLAN. Valid values are within the range [552, 65535].",
        default=DEFAULT_MTU,
        ge=552,
        le=65535,
    )

    space_id: Optional[int] = Field(
        description="The space this VLAN should be placed in. If not specified, the VLAN will be "
        "placed in the 'undefined' space."
    )

    async def to_builder(
        self, services: ServiceCollectionV3, vlan_id: int | None = None
    ) -> VlanBuilder:
        return VlanBuilder(
            name=self.name,
            description=self.description,
            vid=self.vid,
            mtu=self.mtu,
            dhcp_on=False,
            space_id=self.space_id,
        )


class VlanUpdateRequest(VlanCreateRequest):
    fabric_id: int = Field(
        description="Fabric ID containing the VLAN.",
    )

    dhcp_on: bool = Field(
        description="Whether or not DHCP should be managed on the VLAN."
    )

    primary_rack_id: Optional[int] = Field(
        description="The primary rack controller ID managing the VLAN.",
        default=None,
    )

    secondary_rack_id: Optional[int] = Field(
        description="The secondary rack controller ID managing the VLAN",
        default=None,
    )

    relay_vlan_id: Optional[int] = Field(
        description="Relay VLAN ID. Only set when this VLAN will be using a DHCP relay to forward DHCP requests to another VLAN that MAAS is managing. MAAS will not run the DHCP relay itself, it must be configured to proxy reqests to the primary and/or secondary rack controller interfaces for the VLAN specified in this field.",
        default=None,
    )

    async def to_builder(
        self, services: ServiceCollectionV3, vlan_id: int | None = None
    ) -> VlanBuilder:
        assert vlan_id is not None
        # Validate the fields first.
        if self.dhcp_on:
            if self.relay_vlan_id:
                raise ValidationException.build_for_field(
                    "relay_vlan_id",
                    "'relay_vlan_id' cannot be set when dhcp is on.",
                )
            if self.primary_rack_id is None:
                raise ValidationException.build_for_field(
                    "primary_rack_id",
                    "dhcp can only be turned on when a primary rack controller is set.",
                )
            if self.primary_rack_id == self.secondary_rack_id:
                raise ValidationException.build_for_field(
                    "secondary_rack_id",
                    "The primary and secondary rack must be different.",
                )
            node_ids = [self.primary_rack_id]
            if self.secondary_rack_id:
                node_ids.append(self.secondary_rack_id)

            racks = await services.nodes.get_many(
                query=QuerySpec(
                    ClauseFactory.and_clauses(
                        [
                            ClauseFactory.or_clauses(
                                [
                                    NodeClauseFactory.with_type(
                                        NodeTypeEnum.REGION_AND_RACK_CONTROLLER
                                    ),
                                    NodeClauseFactory.with_type(
                                        NodeTypeEnum.RACK_CONTROLLER
                                    ),
                                ]
                            ),
                            NodeClauseFactory.with_ids(node_ids),
                        ]
                    )
                )
            )
            if len(racks) != len(node_ids):
                unknown_ids = set(node_ids) - set([rack.id for rack in racks])
                raise ValidationException.build_for_field(
                    "secondary_rack_id",
                    f"Unknown rack controllers with ids {unknown_ids}",
                )

            # There must be at least one subnet with a dynamic range defined.
            vlan_subnets = await services.subnets.get_many(
                query=QuerySpec(SubnetClauseFactory.with_vlan_id(vlan_id))
            )
            dynamic_ranges = await services.ipranges.get_many(
                query=QuerySpec(
                    IPRangeClauseFactory.with_subnet_ids(
                        [subnet.id for subnet in vlan_subnets]
                    )
                )
            )
            if not dynamic_ranges:
                raise ValidationException(
                    details=[
                        BaseExceptionDetail(
                            type=MISSING_DYNAMIC_RANGE_VIOLATION_TYPE,
                            message="dhcp can only be turned on when a dynamic IP range is defined.",
                        )
                    ]
                )

            # Fix LP: #1798476 - When setting the secondary rack and the primary
            # rack was originally set (and not being changed), require the primary
            # rack to be up and running.
            current_vlan = await services.vlans.get_by_id(vlan_id)
            assert current_vlan is not None
            if (
                current_vlan.primary_rack_id is not None
                and self.secondary_rack_id is not None
                and self.secondary_rack_id != current_vlan.secondary_rack_id
                and self.primary_rack_id == current_vlan.primary_rack_id
            ):
                rackd_service = await services.service_status.get_one(
                    query=QuerySpec(
                        ClauseFactory.and_clauses(
                            [
                                ServiceStatusClauseFactory.with_node_id(
                                    self.primary_rack_id
                                ),
                                ServiceStatusClauseFactory.with_name(
                                    ServiceName.RACKD
                                ),
                            ]
                        )
                    )
                )
                if (
                    rackd_service
                    and rackd_service.status == ServiceStatusEnum.DEAD
                ):
                    raise ValidationException.build_for_field(
                        "secondary_rack_id",
                        "The primary rack controller must be up and running to "
                        "set a secondary rack controller. Without the primary "
                        "the secondary DHCP service will not be able to "
                        "synchronize, preventing it from responding to DHCP "
                        "requests.",
                    )
        elif self.relay_vlan_id is not None:
            if self.relay_vlan_id == vlan_id:
                raise ValidationException.build_for_field(
                    "relay_vlan_id",
                    "'relay_vlan_id' can't match the current VLAN id.",
                )
            if self.primary_rack_id is not None:
                raise ValidationException.build_for_field(
                    "primary_rack_id",
                    "'primary_rack_id' cannot be set when 'relay_vlan_id' is set.",
                )
            if self.secondary_rack_id is not None:
                raise ValidationException.build_for_field(
                    "secondary_rack_id",
                    "'secondary_rack_id' cannot be set when 'relay_vlan_id' is set.",
                )

            relayed_vlan = await services.vlans.get_one(
                query=QuerySpec(VlansClauseFactory.with_id(self.relay_vlan_id))
            )
            if not relayed_vlan:
                raise ValidationException.build_for_field(
                    "relay_vlan_id",
                    f"The relayed VLAN with id '{self.relay_vlan_id}' does not exist.",
                )
            if relayed_vlan.relay_vlan_id is not None:
                raise ValidationException.build_for_field(
                    "relay_vlan_id",
                    f"The relayed VLAN with id '{self.relay_vlan_id}' is "
                    f"already relayed to another VLAN.",
                )

        builder = await super().to_builder(services)
        builder.dhcp_on = self.dhcp_on
        builder.primary_rack_id = self.primary_rack_id
        builder.secondary_rack_id = self.secondary_rack_id
        builder.relay_vlan_id = self.relay_vlan_id
        return builder
