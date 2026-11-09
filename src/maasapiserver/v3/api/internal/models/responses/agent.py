# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Self

from pydantic import Field

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
)
from maasservicelayer.models.agents import Agent
from maasservicelayer.models.dhcp import (
    DHCPDataForAgent,
    InterfaceData,
    IPRangeData,
    KeaHAConfig,
    SubnetData,
    VlanData,
)


class AgentResponse(HalResponse[BaseHal]):
    kind: str = Field(default="Agent")
    id: int
    rack_id: int
    rackcontroller_id: int | None = None

    @classmethod
    def from_model(cls, agent: Agent, self_base_hyperlink: str) -> Self:
        return cls(
            id=agent.id,
            rack_id=agent.rack_id,
            rackcontroller_id=agent.rackcontroller_id,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{agent.id}"
                )
            ),
        )


class AgentConfigResponse(HalResponse[BaseHal]):
    kind: str = Field(default="AgentSignedCertificate")
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


class AgentDHCPDataResponse(HalResponse[BaseHal]):
    kind: str = Field(default="AgentDHCPData")
    vlans: list[VlanData]
    subnets: list[SubnetData]
    ipranges: list[IPRangeData]
    interfaces: list[InterfaceData]
    default_dns_servers: list[str]
    ntp_servers: list[str]
    ha_data: list[KeaHAConfig]

    @classmethod
    def from_model(
        cls, dhcp_data: DHCPDataForAgent, self_base_hyperlink: str
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


class AgentSignedCertificateResponse(HalResponse[BaseHal]):
    kind: str = Field(default="AgentSignedCertificate")
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
