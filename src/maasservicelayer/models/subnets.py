# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from pydantic import IPvAnyAddress

from maascommon.enums.subnet import RdnsMode
from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)
from maasservicelayer.models.fields import IPv4v6Network


@generate_builder()
class Subnet(MaasTimestampedBaseModel):
    name: Optional[str]
    description: Optional[str]
    cidr: IPv4v6Network
    rdns_mode: RdnsMode
    gateway_ip: Optional[IPvAnyAddress]
    dns_servers: Optional[list[str]]
    allow_dns: bool
    allow_proxy: bool
    active_discovery: bool
    managed: bool
    disabled_boot_architectures: list[str]
    vlan_id: int
