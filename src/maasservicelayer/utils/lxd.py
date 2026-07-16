# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Pydantic models for the machine-resources commissioning output.

These models mirror the JSON produced by the `machine-resources` binary
(`src/host-info/cmd/machine-resources`), which is emitted by the
`50-maas-01-commissioning` script. The structures come from the vendored
LXD API code (`shared/api/resource.go` and `shared/api/network.go`) plus
a small MAAS-specific host info envelope defined in `src/host-info/pkg/info/info.go`.

Fields are intentionally lenient (optional with sensible defaults) so that
output from older LXD versions, which may omit fields controlled by API
extensions, can still be parsed. Field names match the JSON keys emitted by
LXD; aliases are only used where the JSON key is not a valid Python
identifier (e.g. the MAAS-injected `machine-extra`/`storage-extra` keys).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _LXDModel(BaseModel):
    # Ignore unknown keys so new LXD fields don't break parsing, and allow
    # populating by field name in addition to alias.
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _treat_null_as_missing(cls, data: Any) -> Any:
        # Different producers (LXD versions, test generators) emit explicit
        # ``null`` for absent values. Drop those keys so the field default is
        # used instead, matching how the commissioning hooks treat missing and
        # None values uniformly.
        if isinstance(data, dict):
            return {
                key: value for key, value in data.items() if value is not None
            }
        return data


# ---------------------------------------------------------------------------
# CPU (ResourcesCPU)
# ---------------------------------------------------------------------------


class LXDCPUCache(_LXDModel):
    level: int = 0
    type: str = ""
    size: int = 0


class LXDCPUThread(_LXDModel):
    id: int = 0
    numa_node: int = 0
    thread: int = 0
    online: bool = False
    isolated: bool = False


class LXDCPUCore(_LXDModel):
    core: int = 0
    die: int = 0
    threads: list[LXDCPUThread] = Field(default_factory=list)
    frequency: int = 0


class LXDCPUSocket(_LXDModel):
    name: str = ""
    vendor: str = ""
    socket: int = 0
    cache: list[LXDCPUCache] = Field(default_factory=list)
    cores: list[LXDCPUCore] = Field(default_factory=list)
    frequency: int = 0
    frequency_minimum: int = 0
    frequency_turbo: int = 0


class LXDCPU(_LXDModel):
    architecture: str = ""
    sockets: list[LXDCPUSocket] = Field(default_factory=list)
    total: int = 0


# ---------------------------------------------------------------------------
# Memory (ResourcesMemory)
# ---------------------------------------------------------------------------


class LXDMemoryNode(_LXDModel):
    numa_node: int = 0
    hugepages_used: int = 0
    hugepages_total: int = 0
    used: int = 0
    total: int = 0


class LXDMemory(_LXDModel):
    nodes: list[LXDMemoryNode] = Field(default_factory=list)
    hugepages_total: int = 0
    hugepages_used: int = 0
    hugepages_size: int = 0
    used: int = 0
    total: int = 0


# ---------------------------------------------------------------------------
# GPU (ResourcesGPU)
# ---------------------------------------------------------------------------


class LXDGPUCardDRM(_LXDModel):
    id: int = 0
    card_name: str = ""
    card_device: str = ""
    control_name: str = ""
    control_device: str = ""
    render_name: str = ""
    render_device: str = ""


class LXDGPUCardSRIOV(_LXDModel):
    current_vfs: int = 0
    maximum_vfs: int = 0
    # LXD emits null when the card exposes no VFs.
    vfs: list[LXDGPUCard] | None = Field(default_factory=list)


class LXDGPUCardNvidia(_LXDModel):
    cuda_version: str = ""
    nvrm_version: str = ""
    brand: str = ""
    model: str = ""
    uuid: str = ""
    architecture: str = ""
    card_name: str = ""
    card_device: str = ""


class LXDGPUCardMdev(_LXDModel):
    api: str = ""
    available: int = 0
    name: str = ""
    description: str = ""
    devices: list[str] = Field(default_factory=list)


class LXDGPUCard(_LXDModel):
    driver: str = ""
    driver_version: str = ""
    drm: LXDGPUCardDRM | None = None
    sriov: LXDGPUCardSRIOV | None = None
    nvidia: LXDGPUCardNvidia | None = None
    mdev: dict[str, LXDGPUCardMdev] = Field(default_factory=dict)
    numa_node: int = 0
    pci_address: str = ""
    vendor: str = ""
    vendor_id: str = ""
    product: str = ""
    product_id: str = ""
    usb_address: str = ""


class LXDGPU(_LXDModel):
    cards: list[LXDGPUCard] = Field(default_factory=list)
    total: int = 0


# ---------------------------------------------------------------------------
# Network (ResourcesNetwork)
# ---------------------------------------------------------------------------


class LXDNetworkCardPortInfiniband(_LXDModel):
    issm_name: str = ""
    issm_device: str = ""
    mad_name: str = ""
    mad_device: str = ""
    verb_name: str = ""
    verb_device: str = ""


class LXDNetworkCardPort(_LXDModel):
    id: str = ""
    address: str = ""
    port: int = 0
    protocol: str = ""
    supported_modes: list[str] = Field(default_factory=list)
    supported_ports: list[str] = Field(default_factory=list)
    port_type: str = ""
    transceiver_type: str = ""
    auto_negotiation: bool = False
    link_detected: bool = False
    link_speed: int = 0
    link_duplex: str = ""
    infiniband: LXDNetworkCardPortInfiniband | None = None


class LXDNetworkCardSRIOV(_LXDModel):
    current_vfs: int = 0
    maximum_vfs: int = 0
    # LXD emits null when the card exposes no VFs.
    vfs: list[LXDNetworkCard] | None = Field(default_factory=list)


class LXDNetworkCardVDPA(_LXDModel):
    name: str = ""
    device: str = ""


class LXDNetworkCard(_LXDModel):
    driver: str = ""
    driver_version: str = ""
    ports: list[LXDNetworkCardPort] = Field(default_factory=list)
    sriov: LXDNetworkCardSRIOV | None = None
    vdpa: LXDNetworkCardVDPA | None = None
    numa_node: int = 0
    pci_address: str = ""
    vendor: str = ""
    vendor_id: str = ""
    product: str = ""
    product_id: str = ""
    firmware_version: str = ""
    usb_address: str = ""


class LXDNetwork(_LXDModel):
    cards: list[LXDNetworkCard] = Field(default_factory=list)
    total: int = 0


# ---------------------------------------------------------------------------
# Storage (ResourcesStorage)
# ---------------------------------------------------------------------------


class LXDStorageDiskPartition(_LXDModel):
    id: str = ""
    device: str = ""
    read_only: bool = False
    size: int = 0
    partition: int = 0
    mounted: bool = False
    device_fs_uuid: str = ""


class LXDStorageDisk(_LXDModel):
    id: str = ""
    device: str = ""
    model: str = ""
    type: str = ""
    read_only: bool = False
    mounted: bool = False
    size: int = 0
    removable: bool = False
    wwn: str = ""
    numa_node: int = 0
    device_path: str = ""
    block_size: int = 0
    firmware_version: str = ""
    rpm: int = 0
    serial: str = ""
    device_id: str = ""
    partitions: list[LXDStorageDiskPartition] = Field(default_factory=list)
    pci_address: str = ""
    usb_address: str = ""
    device_fs_uuid: str = ""
    used_by: str = ""


class LXDStorage(_LXDModel):
    disks: list[LXDStorageDisk] = Field(default_factory=list)
    total: int = 0


# ---------------------------------------------------------------------------
# USB (ResourcesUSB)
# ---------------------------------------------------------------------------


class LXDUSBDeviceInterface(_LXDModel):
    class_: str = Field(default="", alias="class")
    class_id: int = 0
    driver: str = ""
    driver_version: str = ""
    number: int = 0
    subclass: str = ""
    subclass_id: int = 0


class LXDUSBDevice(_LXDModel):
    bus_address: int = 0
    device_address: int = 0
    serial: str = ""
    interfaces: list[LXDUSBDeviceInterface] = Field(default_factory=list)
    vendor: str = ""
    vendor_id: str = ""
    product: str = ""
    product_id: str = ""
    speed: float = 0.0


class LXDUSB(_LXDModel):
    devices: list[LXDUSBDevice] = Field(default_factory=list)
    total: int = 0


# ---------------------------------------------------------------------------
# PCI (ResourcesPCI)
# ---------------------------------------------------------------------------


class LXDPCIVPD(_LXDModel):
    product_name: str = ""
    entries: dict[str, str] = Field(default_factory=dict)


class LXDPCIDevice(_LXDModel):
    driver: str = ""
    driver_version: str = ""
    numa_node: int = 0
    pci_address: str = ""
    vendor: str = ""
    vendor_id: str = ""
    product: str = ""
    product_id: str = ""
    iommu_group: int = 0
    vpd: LXDPCIVPD = Field(default_factory=LXDPCIVPD)


class LXDPCI(_LXDModel):
    devices: list[LXDPCIDevice] = Field(default_factory=list)
    total: int = 0


# ---------------------------------------------------------------------------
# System (ResourcesSystem)
# ---------------------------------------------------------------------------


class LXDSystemFirmware(_LXDModel):
    vendor: str = ""
    date: str = ""
    version: str = ""


class LXDSystemChassis(_LXDModel):
    vendor: str = ""
    type: str = ""
    serial: str = ""
    version: str = ""


class LXDSystemMotherboard(_LXDModel):
    vendor: str = ""
    product: str = ""
    serial: str = ""
    version: str = ""


class LXDSystem(_LXDModel):
    uuid: str = ""
    vendor: str = ""
    product: str = ""
    family: str = ""
    version: str = ""
    sku: str = ""
    serial: str = ""
    type: str = ""
    firmware: LXDSystemFirmware | None = None
    chassis: LXDSystemChassis | None = None
    motherboard: LXDSystemMotherboard | None = None


# ---------------------------------------------------------------------------
# Resources (top-level lxdapi.Resources)
# ---------------------------------------------------------------------------


class LXDResources(_LXDModel):
    cpu: LXDCPU = Field(default_factory=LXDCPU)
    memory: LXDMemory = Field(default_factory=LXDMemory)
    gpu: LXDGPU = Field(default_factory=LXDGPU)
    network: LXDNetwork = Field(default_factory=LXDNetwork)
    storage: LXDStorage = Field(default_factory=LXDStorage)
    usb: LXDUSB = Field(default_factory=LXDUSB)
    pci: LXDPCI = Field(default_factory=LXDPCI)
    system: LXDSystem = Field(default_factory=LXDSystem)


# ---------------------------------------------------------------------------
# Networks (map of interface name -> lxdapi.NetworkState)
# ---------------------------------------------------------------------------


class LXDNetworkStateAddress(_LXDModel):
    family: str = ""
    address: str = ""
    netmask: str = ""
    scope: str = ""


class LXDNetworkStateCounters(_LXDModel):
    bytes_received: int = 0
    bytes_sent: int = 0
    packets_received: int = 0
    packets_sent: int = 0


class LXDNetworkStateBond(_LXDModel):
    mode: str = ""
    transmit_policy: str = ""
    up_delay: int = 0
    down_delay: int = 0
    mii_frequency: int = 0
    mii_state: str = ""
    lower_devices: list[str] | None = Field(default_factory=list)


class LXDNetworkStateBridge(_LXDModel):
    id: str = ""
    stp: bool = False
    forward_delay: int = 0
    vlan_default: int = 0
    vlan_filtering: bool = False
    upper_devices: list[str] | None = Field(default_factory=list)


class LXDNetworkStateVLAN(_LXDModel):
    lower_device: str = ""
    vid: int = 0


class LXDNetworkStateOVN(_LXDModel):
    chassis: str = ""


class LXDNetworkState(_LXDModel):
    addresses: list[LXDNetworkStateAddress] = Field(default_factory=list)
    counters: LXDNetworkStateCounters = Field(
        default_factory=LXDNetworkStateCounters
    )
    hwaddr: str = ""
    mtu: int = 0
    state: str = ""
    type: str = ""
    bond: LXDNetworkStateBond | None = None
    bridge: LXDNetworkStateBridge | None = None
    vlan: LXDNetworkStateVLAN | None = None
    ovn: LXDNetworkStateOVN | None = None


# ---------------------------------------------------------------------------
# Host info envelope (src/host-info/pkg/info/info.go)
# ---------------------------------------------------------------------------


class LXDServerEnvironment(_LXDModel):
    kernel: str = ""
    kernel_architecture: str = ""
    kernel_version: str = ""
    os_name: str = ""
    os_version: str = ""
    server: str = ""
    server_name: str = ""
    server_version: str = ""


class LXDMachineExtra(_LXDModel):
    """MAAS-specific machine metadata injected during commissioning."""

    platform: str = ""


class MachineResources(_LXDModel):
    """Full output of the ``50-maas-01-commissioning`` script.

    This is the ``AllInfo`` structure produced by the ``machine-resources``
    binary, plus the ``machine-extra`` and ``storage-extra`` keys that MAAS
    injects into the commissioning payload before processing.
    """

    api_version: str = ""
    api_extensions: list[str] = Field(default_factory=list)
    environment: LXDServerEnvironment = Field(
        default_factory=LXDServerEnvironment
    )
    resources: LXDResources = Field(default_factory=LXDResources)
    networks: dict[str, LXDNetworkState] = Field(default_factory=dict)
    machine_extra: LXDMachineExtra | None = Field(
        default=None, alias="machine-extra"
    )
    storage_extra: dict | None = Field(default=None, alias="storage-extra")


# Resolve forward references for self-referential SRIOV VF lists.
LXDGPUCardSRIOV.model_rebuild()
LXDNetworkCardSRIOV.model_rebuild()
