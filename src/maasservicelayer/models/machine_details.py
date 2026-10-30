# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from decimal import Decimal

from pydantic import BaseModel


class MachineRecord(BaseModel):
    """Machine-list read projection, independent of request permissions."""

    id: int
    system_id: str
    hostname: str
    description: str
    domain_id: int | None
    domain_name: str | None
    pool_id: int | None
    pool_name: str | None
    owner: str
    parent: str | None
    error_description: str
    zone_id: int | None
    zone_name: str | None
    cpu_count: int
    memory: Decimal
    power_state: str
    locked: bool
    fqdn: str
    tags: list[int]
    physical_disk_count: int
    storage: float
    architecture: str | None
    osystem: str
    distro_series: str
    status_code: int
    ephemeral_deploy: bool
    fabrics: list[str | None]
    spaces: list[str | None]
    extra_macs: list[str | None]
    pxe_mac: str | None
    power_type: str | None
    status_message: str | None
    boot_vlan_id: int | None
    boot_vlan_name: str
    boot_fabric_id: int | None
    boot_fabric_name: str | None
    ips: list[str]
    is_boot_ips: list[bool]
    testing_status_combined: int
    storage_test_status_combined: int
    network_test_status_combined: int
    cpu_test_status_combined: int
    memory_test_status_combined: int
    is_dpu: bool
