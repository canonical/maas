#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

from pydantic import ValidationError
import pytest

from maasapiserver.v3.api.public.models.requests.vlans import (
    VlanCreateRequest,
    VlanUpdateRequest,
)
from maascommon.enums.ipranges import IPRangeType
from maascommon.enums.node import NodeStatus, NodeTypeEnum
from maascommon.enums.power import PowerState
from maascommon.enums.service import ServiceName, ServiceStatusEnum
from maasservicelayer.exceptions.catalog import ValidationException
from maasservicelayer.models.ipranges import IPRange
from maasservicelayer.models.nodes import Node
from maasservicelayer.models.service_status import ServiceStatus
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.models.vlans import Vlan
from maasservicelayer.services import (
    IPRangesService,
    NodesService,
    ServiceCollectionV3,
    ServiceStatusService,
    SubnetsService,
    VlansService,
)


class TestVlanCreateRequest:
    @pytest.mark.asyncio
    async def test_to_builder(self):
        resource = await VlanCreateRequest(vid=0).to_builder(
            Mock(ServiceCollectionV3)
        )
        assert resource.dhcp_on is False
        assert resource.vid == 0
        assert resource.mtu == 1500

    @pytest.mark.parametrize(
        "mtu, is_valid",
        [
            (0, False),
            (551, False),
            (552, True),
            (1000, True),
            (65535, True),
            (65536, False),
        ],
    )
    def test_mtu_validation(self, mtu: int, is_valid: bool) -> None:
        if is_valid:
            VlanCreateRequest(mtu=mtu)
        else:
            with pytest.raises(ValidationError):
                VlanCreateRequest(mtu=mtu)

    @pytest.mark.parametrize(
        "vid, is_valid",
        [
            (-1, False),
            (0, True),
            (1000, True),
            (4094, True),
            (4095, False),
        ],
    )
    def test_vid_validation(self, vid: int, is_valid: bool) -> None:
        if is_valid:
            VlanCreateRequest(vid=vid)
        else:
            with pytest.raises(ValidationError):
                VlanCreateRequest(vid=vid)


@pytest.mark.asyncio
class TestVlanUpdateRequest:
    async def test_required_params(self):
        builder = await VlanUpdateRequest(
            vid=0, dhcp_on=False, fabric_id=0
        ).to_builder(Mock(ServiceCollectionV3), 0)
        assert builder.dhcp_on is False
        assert builder.vid == 0

    async def test_dhcp_on_is_not_null(self):
        with pytest.raises(ValidationError) as e:
            await VlanUpdateRequest(vid=0, fabric_id=0).to_builder(
                Mock(ServiceCollectionV3), 0
            )
        assert len(e.value.errors()) == 1
        assert e.value.errors()[0]["loc"][0] == "dhcp_on"

    async def test_relay_incompatible_with_dhcp_on(self):
        with pytest.raises(ValidationException) as e:
            await VlanUpdateRequest(
                vid=0, dhcp_on=True, relay_vlan_id=1, fabric_id=0
            ).to_builder(Mock(ServiceCollectionV3), 0)
        assert len(e.value.details) == 1
        assert e.value.details[0].field == "relay_vlan_id"
        assert (
            e.value.details[0].message
            == "'relay_vlan_id' cannot be set when dhcp is on."
        )

    async def test_relay_matches_id(self):
        with pytest.raises(ValidationException) as e:
            await VlanUpdateRequest(
                vid=0, dhcp_on=False, relay_vlan_id=0, fabric_id=0
            ).to_builder(Mock(ServiceCollectionV3), 0)
        assert len(e.value.details) == 1
        assert e.value.details[0].field == "relay_vlan_id"
        assert (
            e.value.details[0].message
            == "'relay_vlan_id' can't match the current VLAN id."
        )

    async def test_relay_incompatible_with_primary_rack(self):
        with pytest.raises(ValidationException) as e:
            await VlanUpdateRequest(
                vid=0,
                dhcp_on=False,
                relay_vlan_id=1,
                primary_rack_id=0,
                fabric_id=0,
            ).to_builder(Mock(ServiceCollectionV3), 0)
        assert len(e.value.details) == 1
        assert e.value.details[0].field == "primary_rack_id"
        assert (
            e.value.details[0].message
            == "'primary_rack_id' cannot be set when 'relay_vlan_id' is set."
        )

    async def test_relay_incompatible_with_secondary_rack(self):
        with pytest.raises(ValidationException) as e:
            await VlanUpdateRequest(
                vid=0,
                dhcp_on=False,
                relay_vlan_id=1,
                secondary_rack_id=0,
                fabric_id=0,
            ).to_builder(Mock(ServiceCollectionV3), 0)
        assert len(e.value.details) == 1
        assert e.value.details[0].field == "secondary_rack_id"
        assert (
            e.value.details[0].message
            == "'secondary_rack_id' cannot be set when 'relay_vlan_id' is set."
        )

    async def test_relay_vlan_does_not_exist(self):
        services_mock = Mock(ServiceCollectionV3)
        services_mock.vlans = Mock(VlansService)
        services_mock.vlans.get_one.return_value = None
        with pytest.raises(ValidationException) as e:
            await VlanUpdateRequest(
                vid=0, dhcp_on=False, relay_vlan_id=1, fabric_id=0
            ).to_builder(services_mock, 0)
        assert len(e.value.details) == 1
        assert e.value.details[0].field == "relay_vlan_id"
        assert (
            e.value.details[0].message
            == "The relayed VLAN with id '1' does not exist."
        )

    async def test_relay_vlan_already_relayed(self):
        services_mock = Mock(ServiceCollectionV3)
        services_mock.vlans = Mock(VlansService)
        services_mock.vlans.get_one.return_value = Vlan(
            id=2,
            vid=0,
            description="",
            mtu=1500,
            dhcp_on=False,
            fabric_id=0,
            relay_vlan_id=3,
        )
        with pytest.raises(ValidationException) as e:
            await VlanUpdateRequest(
                vid=0, dhcp_on=False, relay_vlan_id=1, fabric_id=0
            ).to_builder(services_mock, 0)
        assert len(e.value.details) == 1
        assert e.value.details[0].field == "relay_vlan_id"
        assert (
            e.value.details[0].message
            == "The relayed VLAN with id '1' is already relayed to another VLAN."
        )

    async def test_dhcp_on_without_primary_rack(self):
        with pytest.raises(ValidationException) as e:
            await VlanUpdateRequest(
                vid=0, dhcp_on=True, fabric_id=0
            ).to_builder(Mock(ServiceCollectionV3), 0)
        assert len(e.value.details) == 1
        assert e.value.details[0].field == "primary_rack_id"
        assert (
            e.value.details[0].message
            == "dhcp can only be turned on when a primary rack controller is set."
        )

    async def test_dhcp_on_primary_and_secondary_match(self):
        with pytest.raises(ValidationException) as e:
            await VlanUpdateRequest(
                vid=0,
                dhcp_on=True,
                primary_rack_id=0,
                secondary_rack_id=0,
                fabric_id=0,
            ).to_builder(Mock(ServiceCollectionV3), 0)
        assert len(e.value.details) == 1
        # assert e.value.details[0].field == "secondary_rack_id"
        assert (
            e.value.details[0].message
            == "The primary and secondary rack must be different."
        )

    async def test_dhcp_on_unknown_primary(self):
        services_mock = Mock(ServiceCollectionV3)
        services_mock.nodes = Mock(NodesService)
        services_mock.nodes.get_many.return_value = []
        with pytest.raises(ValidationException) as e:
            await VlanUpdateRequest(
                vid=0, dhcp_on=True, primary_rack_id=0, fabric_id=0
            ).to_builder(services_mock, 0)
        assert len(e.value.details) == 1
        assert e.value.details[0].field == "secondary_rack_id"
        assert (
            e.value.details[0].message
            == "Unknown rack controllers with ids {0}"
        )

    async def test_dhcp_on_unknown_secondary(self):
        services_mock = Mock(ServiceCollectionV3)
        services_mock.nodes = Mock(NodesService)
        services_mock.nodes.get_many.return_value = [
            Node(
                id=0,
                system_id="",
                status=NodeStatus.DEPLOYED,
                node_type=NodeTypeEnum.REGION_AND_RACK_CONTROLLER,
                power_state=PowerState.ON,
                hostname="hostname",
            )
        ]
        with pytest.raises(ValidationException) as e:
            await VlanUpdateRequest(
                vid=0,
                dhcp_on=True,
                primary_rack_id=0,
                secondary_rack_id=1,
                fabric_id=0,
            ).to_builder(services_mock, 0)
        assert len(e.value.details) == 1
        assert e.value.details[0].field == "secondary_rack_id"
        assert (
            e.value.details[0].message
            == "Unknown rack controllers with ids {1}"
        )

    async def test_dhcp_on_without_dynamic_ranges(self):
        services_mock = Mock(ServiceCollectionV3)
        services_mock.nodes = Mock(NodesService)
        services_mock.nodes.get_many.return_value = [
            Node(
                id=0,
                system_id="",
                status=NodeStatus.DEPLOYED,
                node_type=NodeTypeEnum.REGION_AND_RACK_CONTROLLER,
                power_state=PowerState.ON,
                hostname="hostname",
            )
        ]
        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.get_many.return_value = [
            Subnet(
                id=0,
                cidr="10.0.0.1",
                rdns_mode=0,
                allow_dns=True,
                allow_proxy=True,
                active_discovery=True,
                managed=True,
                disabled_boot_architectures=[],
                vlan_id=0,
            )
        ]
        services_mock.ipranges = Mock(IPRangesService)
        services_mock.ipranges.get_many.return_value = []

        with pytest.raises(ValidationException) as e:
            await VlanUpdateRequest(
                vid=0, dhcp_on=True, primary_rack_id=0, fabric_id=0
            ).to_builder(services_mock, 0)
        assert len(e.value.details) == 1
        assert e.value.details[0].field is None
        assert (
            e.value.details[0].message
            == "dhcp can only be turned on when a dynamic IP range is defined."
        )

    async def test_dhcp_on_when_primary_is_dead(self):
        services_mock = Mock(ServiceCollectionV3)
        services_mock.nodes = Mock(NodesService)
        services_mock.nodes.get_many.return_value = [
            Node(
                id=0,
                system_id="",
                status=NodeStatus.DEPLOYED,
                node_type=NodeTypeEnum.REGION_AND_RACK_CONTROLLER,
                power_state=PowerState.ON,
                hostname="hostname1",
            ),
            Node(
                id=2,
                system_id="",
                status=NodeStatus.DEPLOYED,
                node_type=NodeTypeEnum.REGION_AND_RACK_CONTROLLER,
                power_state=PowerState.ON,
                hostname="hostname2",
            ),
        ]
        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.get_many.return_value = [
            Subnet(
                id=0,
                cidr="10.0.0.1",
                rdns_mode=0,
                allow_dns=True,
                allow_proxy=True,
                active_discovery=True,
                managed=True,
                disabled_boot_architectures=[],
                vlan_id=0,
            )
        ]
        services_mock.ipranges = Mock(IPRangesService)
        services_mock.ipranges.get_many.return_value = [
            IPRange(
                id=0,
                type=IPRangeType.DYNAMIC,
                start_ip="10.0.0.100",
                end_ip="10.0.0.105",
                subnet_id=0,
                user_id=0,
            )
        ]
        services_mock.vlans = Mock(VlansService)
        services_mock.vlans.get_by_id.return_value = Vlan(
            id=0,
            vid=0,
            description="",
            mtu=1500,
            dhcp_on=True,
            fabric_id=0,
            primary_rack_id=0,
            secondary_rack_id=1,
        )

        services_mock.service_status = Mock(ServiceStatusService)
        services_mock.service_status.get_one.return_value = ServiceStatus(
            id=0,
            name=ServiceName.RACKD,
            status=ServiceStatusEnum.DEAD,
            status_info="",
            node_id=0,
        )

        with pytest.raises(ValidationException) as e:
            await VlanUpdateRequest(
                vid=0,
                dhcp_on=True,
                primary_rack_id=0,
                secondary_rack_id=2,
                fabric_id=0,
            ).to_builder(services_mock, 0)
        assert len(e.value.details) == 1
        assert e.value.details[0].field == "secondary_rack_id"
        assert e.value.details[0].message == (
            "The primary rack controller must be up and running to set a secondary rack controller. "
            "Without the primary "
            "the secondary DHCP service will not be able to "
            "synchronize, preventing it from responding to DHCP "
            "requests."
        )
