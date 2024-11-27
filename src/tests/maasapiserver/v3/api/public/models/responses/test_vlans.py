# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasapiserver.v3.api.public.models.responses.vlans import VlanResponse
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.models.vlans import Vlan
from maasservicelayer.utils.date import utcnow


class TestVlanResponse:
    def test_from_model(self) -> None:
        now = utcnow()
        vlan = Vlan(
            id=0,
            created=now,
            updated=now,
            vid=0,
            name=None,
            description="",
            mtu=0,
            dhcp_on=True,
            external_dhcp="192.0.1.1",
            primary_rack_id=1,
            secondary_rack_id=None,
            relay_vlan=1,
            fabric_id=0,
            space_id=1,
        )
        vlan_response = VlanResponse.from_model(
            vlan=vlan, self_base_hyperlink=f"{V3_API_PREFIX}/vlans"
        )
        assert vlan.id == vlan_response.id
        assert vlan.vid == vlan_response.vid
        assert vlan.name == vlan_response.name
        assert vlan.description == vlan_response.description
        assert vlan.mtu == vlan_response.mtu
        assert vlan.dhcp_on == vlan_response.dhcp_on
        assert vlan.external_dhcp == vlan_response.external_dhcp
        assert vlan.primary_rack_id == vlan_response.primary_rack
        assert vlan.secondary_rack_id == vlan_response.secondary_rack
        assert vlan.relay_vlan_id == vlan_response.relay_vlan_id
        assert vlan_response.space.href.endswith(f"spaces/{vlan.space_id}")
