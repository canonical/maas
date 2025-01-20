# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any, Optional

from pydantic import Field, IPvAnyAddress, validator

from maasapiserver.v3.api.public.models.requests.base import (
    OptionalNamedBaseModel,
)
from maascommon.bootmethods import find_boot_method_by_arch_or_octet
from maascommon.enums.subnet import RdnsMode
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    ValidationException,
)
from maasservicelayer.exceptions.constants import (
    INVALID_ARGUMENT_VIOLATION_TYPE,
)
from maasservicelayer.models.fields import IPv4v6Network
from maasservicelayer.models.subnets import SubnetBuilder


class SubnetRequest(OptionalNamedBaseModel):
    description: Optional[str] = Field(
        description="The description of the subnet.", default=""
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

    def _validate_boot_architectures(
        self, disabled_boot_architectures: list[str]
    ):
        disabled_boot_method_names = []
        for disabled_arch in disabled_boot_architectures:
            boot_method = find_boot_method_by_arch_or_octet(
                disabled_arch, disabled_arch.replace("0x", "00:")
            )
            if boot_method is None or (
                not boot_method.arch_octet and not boot_method.path_prefix_http
            ):
                raise ValidationException(
                    details=[
                        BaseExceptionDetail(
                            type=INVALID_ARGUMENT_VIOLATION_TYPE,
                            message=f"Unkown boot architecture {disabled_arch}",
                        )
                    ]
                )
            disabled_boot_method_names.append(boot_method.name)
        return disabled_boot_method_names

    def to_builder(self, vlan_id: int) -> SubnetBuilder:
        return SubnetBuilder(
            name=self.name if self.name else str(self.cidr),
            description=self.description,
            cidr=self.cidr,
            rdns_mode=self.rdns_mode,
            gateway_ip=self.gateway_ip,
            dns_servers=[str(dns_server) for dns_server in self.dns_servers],
            allow_dns=self.allow_dns,
            allow_proxy=self.allow_proxy,
            active_discovery=self.active_discovery,
            managed=self.managed,
            disabled_boot_architectures=self._validate_boot_architectures(
                self.disabled_boot_architectures
            ),
            vlan_id=vlan_id,
        )
