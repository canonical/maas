# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Self

from pydantic import Field

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
)
from maasservicelayer.models.dhcp import (
    DHCPDataForRackController,
    InterfaceData,
    IPRangeData,
    KeaHAConfig,
    SubnetData,
    VlanData,
)
from maasservicelayer.models.rackcontrollers import RackController


class RackControllerResponse(HalResponse[BaseHal]):
    kind: str = Field(default="RackController")
    id: int
    rack_id: int
    node_id: int | None = None

    @classmethod
    def from_model(
        cls, rack_controller: RackController, self_base_hyperlink: str
    ) -> Self:
        return cls(
            id=rack_controller.id,
            rack_id=rack_controller.rack_id,
            node_id=rack_controller.node_id,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{rack_controller.id}"
                )
            ),
        )


class RackControllerConfigResponse(HalResponse[BaseHal]):
    kind: str = Field(default="RackControllerSignedCertificate")
    maas_url: str
    rpc_secret: str
    system_id: str
    temporal: dict

    @classmethod
    def from_model(
        cls,
        maas_url: str,
        rpc_secret: str,
        system_id: str,
        temporal: dict,
        self_base_hyperlink: str,
    ) -> Self:
        return cls(
            maas_url=maas_url,
            rpc_secret=rpc_secret,
            system_id=system_id,
            temporal=temporal,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(href=f"{self_base_hyperlink.rstrip('/')}")
            ),
        )


class RackControllerDHCPDataResponse(HalResponse[BaseHal]):
    kind: str = Field(default="RackControllerDHCPData")
    vlans: list[VlanData]
    subnets: list[SubnetData]
    ipranges: list[IPRangeData]
    interfaces: list[InterfaceData]
    default_dns_servers: list[str]
    ntp_servers: list[str]
    ha_data: list[KeaHAConfig]

    @classmethod
    def from_model(
        cls, dhcp_data: DHCPDataForRackController, self_base_hyperlink: str
    ) -> Self:
        return cls(
            vlans=dhcp_data.vlans,
            subnets=dhcp_data.subnets,
            ipranges=dhcp_data.ipranges,
            interfaces=dhcp_data.interfaces,
            default_dns_servers=dhcp_data.default_dns_servers,
            ntp_servers=dhcp_data.ntp_servers,
            ha_data=dhcp_data.ha_data,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(href=f"{self_base_hyperlink.rstrip('/')}")
            ),
        )


class RackControllerSignedCertificateResponse(HalResponse[BaseHal]):
    kind: str = Field(default="RackControllerSignedCertificate")
    certificate: str
    ca: str

    @classmethod
    def from_model(
        cls, certificate: str, ca: str, self_base_hyperlink: str
    ) -> Self:
        return cls(
            certificate=certificate,
            ca=ca,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(href=f"{self_base_hyperlink.rstrip('/')}")
            ),
        )
