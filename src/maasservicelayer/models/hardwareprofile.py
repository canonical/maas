# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import TypeVar

from pydantic import BaseModel

from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)

HwItem = TypeVar("HwItem")


class HardwareGroup[HwItem](BaseModel):
    count: int
    items: list[HwItem]


class HardwareStorageItem(BaseModel):
    name: str
    size_bytes: int
    block_size: int
    id_path: str | None = None
    model: str | None = None
    serial: str | None = None
    firmware_version: str | None = None
    numa_node: int


class HardwareStorageGroup(HardwareGroup[HardwareStorageItem]):
    disk_type: str
    size_bytes: int


class HardwareNetworkItem(BaseModel):
    name: str
    mac_address: str
    link_speed: int
    sriov_max_vf: int
    numa_node: int


class HardwareNetworkGroup(HardwareGroup[HardwareNetworkItem]):
    speed_mbps: int
    vendor: str
    product: str


class HardwareAcceleratorItem(BaseModel):
    vendor_id: str
    product_id: str
    pci_address: str
    numa_node: int


class HardwareAcceleratorGroup(HardwareGroup[HardwareAcceleratorItem]):
    vendor: str
    product: str


@generate_builder()
class HardwareProfile(MaasTimestampedBaseModel):
    node_id: int
    architecture: str
    cpu_cores: int
    cpu_speed_mhz: int
    memory_mb: int
    disk_count: int
    total_storage_bytes: int
    nic_count: int
    gpu_count: int
    system_vendor: str | None = None
    system_product: str | None = None
    hardware_fingerprint: str
    storage: list[HardwareStorageGroup]
    network: list[HardwareNetworkGroup]
    accelerators: list[HardwareAcceleratorGroup]
