# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from collections import defaultdict, OrderedDict
from dataclasses import dataclass, field
from math import ceil
from typing import List, Optional

from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db.models import (
    BooleanField,
    CASCADE,
    CharField,
    F,
    ForeignKey,
    IntegerField,
    OneToOneField,
    SET_NULL,
    TextField,
)
from django.db.models.functions import Coalesce

from maasserver.fields import MACAddressField
from maasserver.models.bmc import BMC
from maasserver.models.cleansave import CleanSave
from maasserver.models.interface import Interface
from maasserver.models.node import Machine
from maasserver.models.numa import NUMANode
from maasserver.models.timestampedmodel import TimestampedModel
from provisioningserver.drivers.pod import (
    InterfaceAttachType,
    InterfaceAttachTypeChoices,
)

MB = 1024 * 1024


class VirtualMachine(CleanSave, TimestampedModel):
    """A virtual machine managed by a VM host."""

    identifier = TextField()
    pinned_cores = ArrayField(IntegerField(), blank=True, default=list)
    unpinned_cores = IntegerField(default=0, blank=True)
    memory = IntegerField(default=0)
    hugepages_backed = BooleanField(default=False)
    machine = OneToOneField(
        Machine,
        SET_NULL,
        default=None,
        blank=True,
        null=True,
        editable=False,
        related_name="virtualmachine",
    )
    project = TextField(default="", blank=True)
    bmc = ForeignKey(BMC, editable=False, on_delete=CASCADE)

    class Meta:
        unique_together = [("bmc", "identifier", "project")]

    def clean(self):
        super().clean()
        if self.pinned_cores and self.unpinned_cores:
            raise ValidationError(
                "VirtualMachine can't have both pinned and unpinned cores"
            )


class VirtualMachineInterface(CleanSave, TimestampedModel):
    """A NIC inside VM that's connected to the host interface."""

    vm = ForeignKey(
        VirtualMachine,
        editable=False,
        on_delete=CASCADE,
        related_name="interfaces_set",
    )
    mac_address = MACAddressField(null=True, blank=True)
    host_interface = ForeignKey(Interface, null=True, on_delete=SET_NULL)
    attachment_type = CharField(
        max_length=10,
        null=False,
        choices=InterfaceAttachTypeChoices,
    )

    class Meta:
        unique_together = [("vm", "mac_address")]


@dataclass
class NUMAPinningCoresResources:
    """Core usage details for NUMA pinning."""

    allocated: List[int] = field(default_factory=list)
    free: List[int] = field(default_factory=list)


@dataclass
class NUMAPinningGeneralMemoryResources:
    """General memory usage details for NUMA pinning."""

    allocated: int = 0
    free: int = 0


@dataclass
class NUMAPinningHugepagesResources:
    """Hugepages usage details for NUMA pinning."""

    page_size: int
    allocated: int = 0
    free: int = 0


@dataclass
class NUMAPinningMemoryResources:
    """Memory usage details for NUMA pinning."""

    hugepages: List[NUMAPinningHugepagesResources] = field(
        default_factory=list
    )
    general: NUMAPinningGeneralMemoryResources = field(
        default_factory=NUMAPinningGeneralMemoryResources
    )


@dataclass
class NUMAPinningVirtualMachineNetworkResources:
    host_nic_id: int
    guest_nic_id: Optional[int] = None


@dataclass
class NUMAPinningVirtualMachineResources:
    """Resource usage for a VM in a NUMA node."""

    system_id: Optional[str]
    pinned_cores: List[int] = field(default_factory=list)
    networks: List[NUMAPinningVirtualMachineNetworkResources] = field(
        default_factory=list
    )


@dataclass
class NUMAPinningVirtualFunctionResources:
    """Resource usage for network interfaces VFs in a NUMA node."""

    free: int = 0
    allocated: int = 0


@dataclass
class NUMAPinningHostInterfaceResources:
    """Network interfaces details in a NUMA node."""

    id: int
    name: str
    virtual_functions: NUMAPinningVirtualFunctionResources = field(
        default_factory=NUMAPinningVirtualFunctionResources
    )


@dataclass
class NUMAPinningNodeResources:
    """Resource usage for a NUMA node."""

    node_id: int
    memory: NUMAPinningMemoryResources = field(
        default_factory=NUMAPinningMemoryResources
    )
    cores: NUMAPinningCoresResources = field(
        default_factory=NUMAPinningCoresResources
    )
    vms: List[NUMAPinningVirtualMachineResources] = field(default_factory=list)
    interfaces: List[NUMAPinningHostInterfaceResources] = field(
        default_factory=list
    )


@dataclass
class VMHostResource:
    """Usage for a resource type in a VM host."""

    allocated_tracked: int = 0
    allocated_other: int = 0
    free: int = 0

    @property
    def allocated(self):
        return self.allocated_tracked + self.allocated_other


@dataclass
class VMHostMemoryResources:
    """Memory usage details for a VM host."""

    hugepages: VMHostResource = field(default_factory=VMHostResource)
    general: VMHostResource = field(default_factory=VMHostResource)


@dataclass
class VMHostResources:
    """Resources for a VM host."""

    cores: VMHostResource = field(default_factory=VMHostResource)
    memory: VMHostMemoryResources = field(
        default_factory=VMHostMemoryResources
    )
    numa: List[NUMAPinningNodeResources] = field(default_factory=list)


def get_vm_host_resources(pod):
    """Return used resources for a VM host by its ID."""
    resources = VMHostResources()
    if pod.host is None:
        return resources

    vms = list(
        VirtualMachine.objects.annotate(
            system_id=Coalesce("machine__system_id", None)
        )
        .filter(bmc=pod)
        .all()
    )
    numanodes = OrderedDict(
        (node.index, node)
        for node in NUMANode.objects.prefetch_related("hugepages_set")
        .filter(node=pod.host)
        .order_by("index")
        .all()
    )

    total_memory = 0
    total_cores = 0
    total_hugepages = 0
    # to track how many cores are not used by pinned VMs in each NUMA node
    available_numanode_cores = {}
    # to track how much general memory is allocated in each NUMA node
    allocated_numanode_memory = defaultdict(int)
    # XXX map NUMA nodes to default hugepages entry, since currently LXD only support one size
    numanode_hugepages = {}
    # map NUMA nodes to list of VMs resources in them
    numanode_vms_resources = defaultdict(list)
    allocated_numanode_hugepages = defaultdict(int)
    for numa_idx, numa_node in numanodes.items():
        available_numanode_cores[numa_idx] = set(numa_node.cores)
        hugepages = numa_node.hugepages_set.first()
        numanode_hugepages[numa_idx] = hugepages
        # update global totals
        total_cores += len(numa_node.cores)
        total_memory += numa_node.memory * MB
        if hugepages:
            total_hugepages += hugepages.total

    numanode_interfaces = defaultdict(list)
    for interface in Interface.objects.annotate(
        numa_index=F("numa_node__index")
    ).filter(node=pod.host):
        interface.allocated_vfs = 0
        numanode_interfaces[interface.numa_index].append(interface)
    all_vm_interfaces = (
        VirtualMachineInterface.objects.filter(
            vm__in=vms, host_interface__isnull=False
        )
        .annotate(numa_index=F("host_interface__numa_node__index"))
        .all()
    )
    vm_interfaces = defaultdict(list)
    for vm_interface in all_vm_interfaces:
        vm_interfaces[vm_interface.vm_id].append(vm_interface)

    tracked_project = pod.power_parameters.get("project")
    for vm in vms:
        vm_mem = vm.memory * MB
        vm_cores = vm.unpinned_cores + len(vm.pinned_cores)
        if vm.project == tracked_project:
            resources.cores.allocated_tracked += vm_cores
            if vm.hugepages_backed:
                resources.memory.hugepages.allocated_tracked += vm_mem
            else:
                resources.memory.general.allocated_tracked += vm_mem
        else:
            resources.cores.allocated_other += vm_cores
            if vm.hugepages_backed:
                resources.memory.hugepages.allocated_other += vm_mem
            else:
                resources.memory.general.allocated_other += vm_mem
        _update_numanode_resources_usage(
            vm,
            vm_interfaces[vm.id],
            numanodes,
            numanode_hugepages,
            available_numanode_cores,
            allocated_numanode_memory,
            allocated_numanode_hugepages,
            numanode_vms_resources,
            numanode_interfaces,
        )
    resources.cores.free = total_cores - resources.cores.allocated
    resources.memory.general.free = (
        total_memory - resources.memory.general.allocated
    )
    resources.memory.hugepages.free = (
        total_hugepages - resources.memory.hugepages.allocated
    )
    resources.numa = [
        _get_numa_pinning_resources(
            numa_node,
            available_numanode_cores[numa_idx],
            allocated_numanode_memory[numa_idx],
            numanode_hugepages[numa_idx],
            allocated_numanode_hugepages[numa_idx],
            numanode_vms_resources[numa_idx],
            numanode_interfaces,
        )
        for numa_idx, numa_node in numanodes.items()
    ]
    return resources


def _update_numanode_resources_usage(
    vm,
    vm_interfaces,
    numanodes,
    numanode_hugepages,
    available_numanode_cores,
    allocated_numanode_memory,
    allocated_numanode_hugepages,
    numanode_vms_resources,
    numanode_interfaces,
):
    numanode_weights, used_numanode_cores = _get_vm_numanode_weights_and_cores(
        vm, numanodes
    )
    for numa_idx, numa_weight in numanode_weights.items():
        vm_node_memory = int(vm.memory * MB * numa_weight)
        if vm.hugepages_backed:
            hugepages = numanode_hugepages[numa_idx]
            if hugepages:
                # round up to nearest page
                vm_node_memory = (
                    ceil(vm_node_memory / hugepages.page_size)
                    * hugepages.page_size
                )
                allocated_numanode_hugepages[numa_idx] += vm_node_memory
        else:
            allocated_numanode_memory[numa_idx] += vm_node_memory
        if used_numanode_cores[numa_idx]:
            available_numanode_cores[numa_idx].difference_update(
                used_numanode_cores[numa_idx]
            )

    for numa_idx in numanodes.keys():
        pinned_cores = list(used_numanode_cores[numa_idx])
        numa_networks = []
        for vm_interface in vm_interfaces:
            if vm_interface.numa_index != numa_idx:
                continue
            numa_networks.append(
                NUMAPinningVirtualMachineNetworkResources(
                    vm_interface.host_interface_id
                )
            )
            if vm_interface.attachment_type == InterfaceAttachType.SRIOV:
                for host_interface in numanode_interfaces[numa_idx]:
                    if host_interface.id == vm_interface.host_interface_id:
                        host_interface.allocated_vfs += 1

        if pinned_cores or numa_networks:
            numanode_vms_resources[numa_idx].append(
                NUMAPinningVirtualMachineResources(
                    system_id=vm.system_id,
                    pinned_cores=list(used_numanode_cores[numa_idx]),
                    networks=[
                        NUMAPinningVirtualMachineNetworkResources(
                            vm_interface.host_interface_id
                        )
                        for vm_interface in vm_interfaces
                        if vm_interface.numa_index == numa_idx
                    ],
                )
            )


def _get_vm_numanode_weights_and_cores(vm, numanodes):
    """Return dicts mapping NUMA indexes to memory/CPU weights and cores for the VM."""
    vm_cores = set(vm.pinned_cores)
    # map NUMA node indexes to memory/cpu weight for the VM
    numanode_weights = {}
    numanode_cores = defaultdict(set)
    for numa_idx, numa_node in numanodes.items():
        common_cores = vm_cores & set(numa_node.cores)
        if common_cores:
            numanode_weights[numa_idx] = len(common_cores) / len(
                vm.pinned_cores
            )
            vm_cores.difference_update(common_cores)
            numanode_cores[numa_idx] = common_cores
        if not vm_cores:
            # done going through all VM cores
            break

    return numanode_weights, numanode_cores


def _get_numa_pinning_resources(
    numa_node,
    available_numanode_cores,
    allocated_numanode_memory,
    numanode_hugepages,
    allocated_numanode_hugepages,
    numanode_vm_resources,
    numanode_interfaces,
):
    numa_resources = NUMAPinningNodeResources(numa_node.index)
    # fill in cores details
    numa_resources.cores.free = sorted(available_numanode_cores)
    numa_resources.cores.allocated = sorted(
        set(numa_node.cores) - available_numanode_cores
    )
    # fill in memory details
    numa_resources.memory.general.allocated = allocated_numanode_memory
    numa_resources.memory.general.free = (
        numa_node.memory * MB - allocated_numanode_memory
    )
    if numanode_hugepages:
        numa_resources.memory.hugepages.append(
            NUMAPinningHugepagesResources(
                page_size=numanode_hugepages.page_size,
                allocated=allocated_numanode_hugepages,
                free=numanode_hugepages.total - allocated_numanode_hugepages,
            )
        )
        # if hugepages are used, general memory needs to be decreased by the
        # amount reserved for them
        numa_resources.memory.general.free -= numanode_hugepages.total
    numa_resources.vms = numanode_vm_resources
    numa_resources.interfaces = [
        NUMAPinningHostInterfaceResources(
            interface.id,
            interface.name,
            # sriov_max_vf doesn't tell how many VFs are enabled, but
            # we don't have any better data.
            NUMAPinningVirtualFunctionResources(
                free=interface.sriov_max_vf - interface.allocated_vfs,
                allocated=interface.allocated_vfs,
            ),
        )
        for interface in numanode_interfaces[numa_node.index]
    ]
    return numa_resources
