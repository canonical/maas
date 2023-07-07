from typing import Optional

from pydantic import BaseModel


class ModelRef(BaseModel):
    id: int
    name: str


class TestStatus(BaseModel):
    status: Optional[int]
    pending: Optional[int]
    running: Optional[int]
    passed: Optional[int]
    failed: Optional[int]


class Vlan(BaseModel):
    id: Optional[int]
    name: Optional[str]
    fabric_id: Optional[int]
    fabric_name: Optional[str]


class IPAddress(BaseModel):
    ip: Optional[str]
    is_boot: Optional[bool]


class Machine(BaseModel):
    """A MAAS AZ."""

    # maasui/src/src/app/store/machine/types/base.ts

    id: int
    system_id: str
    hostname: str
    description: str
    pool: ModelRef
    pod: Optional[ModelRef]
    domain: ModelRef
    owner: str
    parent: Optional[str]
    error_description: str
    zone: ModelRef
    cpu_count: int
    memory: int
    power_state: str
    locked: bool
    permissions: list[str]
    fqdn: str
    actions: list[str]
    link_type: str
    tags: Optional[list[int]]
    physical_disk_count: Optional[int]
    storage: Optional[float]
    testing_status: Optional[TestStatus]
    architecture: str
    osystem: str
    distro_series: str
    status: str
    status_code: int
    simple_status: str
    fabrics: Optional[list[str]]
    spaces: Optional[list[str]]
    extra_macs: Optional[list[str]]
    status_message: Optional[str]
    pxe_mac: Optional[str]
    vlan: Optional[Vlan]
    power_type: Optional[str]
    ip_addresses: Optional[list[IPAddress]]
    cpu_test_status: Optional[TestStatus]
    memory_test_status: Optional[TestStatus]
    network_test_status: Optional[TestStatus]
    storage_test_status: Optional[TestStatus]
