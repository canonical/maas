# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any, Optional

from pydantic import Field, IPvAnyAddress, validator

from maasapiserver.v3.api.public.models.requests.base import (
    OptionalNamedBaseModel,
)
from maascommon.enums.subnet import RdnsMode
from maasservicelayer.db.repositories.subnets import SubnetResourceBuilder
from maasservicelayer.utils.validators import IPv4v6Network


class SubnetRequest(OptionalNamedBaseModel):
    description: Optional[str] = Field(
        description="The description of the subnet.", default=None
    )
    cidr: IPv4v6Network = Field(
        description="The network CIDR for this subnet."
    )
    rdns_mode: RdnsMode = Field(
        description="How reverse DNS is handled for this subnet. One of:"
        "- ``0`` Disabled: No reverse zone is created."
        "- ``1`` Enabled: Generate reverse zone."
        "- ``2`` RFC2317: Extends '1' to create the necessary parent zone with"
        " the appropriate CNAME resource records for the network, if the"
        " network is small enough to require the support described in RFC2317.",
        default=RdnsMode.DEFAULT,
    )
    gateway_ip: Optional[IPvAnyAddress] = Field(
        description="The gateway IP for this subnet.", default=None
    )
    dns_servers: list[IPvAnyAddress] = Field(
        description="List of DNS servers for the subnet.", default_factory=list
    )
    allow_dns: bool = Field(
        description="Configure MAAS DNS to allow DNS resolution in this subnet.",
        default=True,
    )
    allow_proxy: bool = Field(
        description="Configure maas-proxy to allow requests from this subnet.",
        default=True,
    )
    active_discovery: bool = Field(
        description="Whether to allow active discovery in the subnet.",
        default=True,
    )
    managed: bool = Field(
        description="Whether this subnet is managed by MAAS or not.",
        default=True,
    )
    disabled_boot_architectures: list[str] = Field(
        description="List of disabled boot architectures for this subnet.",
        default_factory=list,
    )

    @validator("gateway_ip")
    def ensure_gatweway_ip_in_cidr(
        cls, v: Optional[IPvAnyAddress], values: dict[str, Any]
    ):
        if v is None:
            return v
        gateway_ip: IPvAnyAddress = v
        network: IPv4v6Network = values["cidr"]
        if gateway_ip in network:
            return gateway_ip
        elif network.version == 6 and gateway_ip.is_link_local:
            # If this is an IPv6 network and the gateway is in the link-local
            # network (fe80::/64 -- required to be configured by the spec),
            # then it is also valid.
            return gateway_ip
        else:
            raise ValueError("gateway IP must be within CIDR range.")

    def to_builder(self) -> SubnetResourceBuilder:
        builder = (
            SubnetResourceBuilder()
            .with_name(self.name if self.name else str(self.cidr))
            .with_description(self.description)
            .with_cidr(self.cidr)
            .with_rdns_mode(self.rdns_mode)
            .with_gateway_ip(self.gateway_ip)
            .with_dns_servers(self.dns_servers)
            .with_allow_dns(self.allow_dns)
            .with_allow_proxy(self.allow_proxy)
            .with_active_discovery(self.active_discovery)
            .with_managed(self.managed)
            .with_disabled_boot_architectures(self.disabled_boot_architectures)
        )
        return builder
