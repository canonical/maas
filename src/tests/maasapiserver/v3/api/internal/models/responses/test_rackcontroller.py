# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasapiserver.v3.api.internal.models.responses.rackcontroller import (
    RackControllerConfigResponse,
    RackControllerDHCPDataResponse,
    RackControllerSignedCertificateResponse,
)
from maasapiserver.v3.constants import V3_INTERNAL_API_PREFIX
from maasservicelayer.models.dhcp import (
    DHCPDataForRackController,
    InterfaceData,
    KeaHAConfig,
    VlanData,
)


class TestRackControllerConfigResponse:
    def test_from_model(self) -> None:
        maas_url = "https://example.com:5240/MAAS"
        rpc_secret = "mock-rpc-secret"
        system_id = "abc123"
        temporal = {"encryption_key": "mock-encryption-key"}
        base_hyperlink = (
            f"{V3_INTERNAL_API_PREFIX}/rack_controllers/mock-uuid/config"
        )

        rack_controller_config_response = (
            RackControllerConfigResponse.from_model(
                maas_url=maas_url,
                rpc_secret=rpc_secret,
                system_id=system_id,
                temporal=temporal,
                self_base_hyperlink=base_hyperlink,
            )
        )

        assert maas_url == rack_controller_config_response.maas_url
        assert rpc_secret == rack_controller_config_response.rpc_secret
        assert system_id == rack_controller_config_response.system_id
        assert temporal == rack_controller_config_response.temporal
        assert (
            "RackControllerSignedCertificate"
            == rack_controller_config_response.kind
        )
        assert (
            base_hyperlink
            == rack_controller_config_response.hal_links.self.href
        )


class TestRackControllerDHCPDataResponse:
    def test_from_model(self) -> None:
        dhcp_data = DHCPDataForRackController(
            vlans=[VlanData(id=1, vid=0, relayed_vlan_id=None, mtu=1500)],
            subnets=[],
            ipranges=[],
            interfaces=[InterfaceData(id=1, vlan_id=1, name="eth0")],
            default_dns_servers=["10.0.0.2"],
            ntp_servers=["10.0.0.3"],
            ha_data=[
                KeaHAConfig(
                    primary_rack_system_id="rack-1",
                    secondary_rack_system_id="rack-2",
                    primary_rack_ip="10.0.0.2",
                    secondary_rack_ip="10.0.0.4",
                )
            ],
        )
        base_hyperlink = f"{V3_INTERNAL_API_PREFIX}/rack_controllers/mock-system-id/dhcp-data"

        response = RackControllerDHCPDataResponse.from_model(
            dhcp_data=dhcp_data, self_base_hyperlink=base_hyperlink
        )

        assert response.kind == "RackControllerDHCPData"
        assert response.vlans == dhcp_data.vlans
        assert response.interfaces == dhcp_data.interfaces
        assert response.default_dns_servers == ["10.0.0.2"]
        assert response.ntp_servers == ["10.0.0.3"]
        assert response.ha_data == dhcp_data.ha_data
        assert response.hal_links.self.href == base_hyperlink


class TestRackControllerSignedCertificateResponse:
    def test_from_model(self) -> None:
        certificate = "certificate"
        ca = "ca"

        rack_controller_cs_response = RackControllerSignedCertificateResponse.from_model(
            certificate=certificate,
            ca=ca,
            self_base_hyperlink=f"{V3_INTERNAL_API_PREFIX}/rack_controllers:enroll",
        )

        assert certificate == rack_controller_cs_response.certificate
        assert (
            f"{V3_INTERNAL_API_PREFIX}/rack_controllers:enroll"
            == rack_controller_cs_response.hal_links.self.href
        )
