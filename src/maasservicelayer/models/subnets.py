# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from pydantic import IPvAnyAddress, IPvAnyNetwork

from maasservicelayer.models.base import MaasTimestampedBaseModel


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
    vlan_id: int
