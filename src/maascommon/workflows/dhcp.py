#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from typing import Any, Optional

# Workflows names
CONFIGURE_DHCP_FOR_AGENT_WORKFLOW_NAME = "configure-dhcp-for-agent"
CONFIGURE_DHCP_WORKFLOW_NAME = "configure-dhcp"


# Workflows parameters
@dataclass
class ConfigureDHCPParam:
    system_ids: Optional[list[str]] = None
    vlan_ids: Optional[list[int]] = None
    subnet_ids: Optional[list[int]] = None
    static_ip_addr_ids: Optional[list[int]] = None
    ip_range_ids: Optional[list[int]] = None
    reserved_ip_ids: Optional[list[int]] = None


@dataclass
class ConfigureDHCPForAgentParam:
    system_id: str
    full_reload: bool
    static_ip_addr_ids: list[int] | None = None
    reserved_ip_ids: list[int] | None = None


def merge_configure_dhcp_param(
    old: ConfigureDHCPParam, new: ConfigureDHCPParam
) -> ConfigureDHCPParam:
    def ensure_list(val: list[Any] | None) -> list[Any]:
        return val if val is not None else []

    return ConfigureDHCPParam(
        system_ids=ensure_list(old.system_ids) + ensure_list(new.system_ids),
        vlan_ids=ensure_list(old.vlan_ids) + ensure_list(new.vlan_ids),
        subnet_ids=ensure_list(old.subnet_ids) + ensure_list(new.subnet_ids),
        static_ip_addr_ids=ensure_list(old.static_ip_addr_ids)
        + ensure_list(new.static_ip_addr_ids),
        ip_range_ids=ensure_list(old.ip_range_ids)
        + ensure_list(new.ip_range_ids),
        reserved_ip_ids=ensure_list(old.reserved_ip_ids)
        + ensure_list(new.ip_range_ids),
    )
