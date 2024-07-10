# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from pydantic import IPvAnyAddress, IPvAnyNetwork

from maasapiserver.v3.api.models.responses.base import BaseHal, BaseHref
from maasapiserver.v3.api.models.responses.subnets import SubnetResponse
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.models.base import MaasTimestampedBaseModel


class Subnet(MaasTimestampedBaseModel):
    name: Optional[str]
    description: Optional[str]
    cidr: IPvAnyNetwork
    # TODO: move RDNS_MODE to enum and change the type here
    rdns_mode: int
    gateway_ip: Optional[IPvAnyAddress]
    dns_servers: Optional[list[str]]
    allow_dns: bool
    allow_proxy: bool
    active_discovery: bool
    managed: bool
    disabled_boot_architectures: list[str]

    def to_response(self, self_base_hyperlink: str) -> SubnetResponse:
        return SubnetResponse(
            id=self.id,
            name=self.name,
            description=self.description,
            vlan=BaseHref(
                href=f"{V3_API_PREFIX}/vlans?filter=subnet_id eq {self.id}"
            ),
            cidr=self.cidr,
            rdns_mode=self.rdns_mode,
            gateway_ip=self.gateway_ip,
            dns_servers=self.dns_servers,
            allow_dns=self.allow_dns,
            allow_proxy=self.allow_proxy,
            active_discovery=self.active_discovery,
            managed=self.managed,
            disabled_boot_architectures=self.disabled_boot_architectures,
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{self.id}"
                )
            ),
        )
