# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from collections import defaultdict
from dataclasses import dataclass, field
from math import ceil
from typing import List

from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db.models import (
    BooleanField,
    CASCADE,
    ForeignKey,
    IntegerField,
    OneToOneField,
    SET_NULL,
    TextField,
)
from django.db.models.functions import Coalesce

from maasserver.models.bmc import BMC
from maasserver.models.cleansave import CleanSave
from maasserver.models.node import Machine
from maasserver.models.numa import NUMANode
from maasserver.models.timestampedmodel import TimestampedModel


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
    bmc = ForeignKey(BMC, editable=False, on_delete=CASCADE)

    class Meta:
        unique_together = [("bmc", "identifier")]

    def clean(self):
        super().clean()
        if self.pinned_cores and self.unpinned_cores:
            raise ValidationError(
                "VirtualMachine can't have both pinned and unpinned cores"
            )


@dataclass
class NUMAPinningCoresResources:
    """Core usage details for NUMA pinning."""

    allocated: List[int] = field(default_factory=list)
    free: List[int] = field(default_factory=list)


@dataclass
class NUMAPinningGeneralMemoryResources:
    """Core usage details for NUMA pinning."""

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
class NUMAPinningVirtualMachineResources:
    """Resource usaage for a VM in a NUMA node."""

    system_id: str
    pinned_cores: List[int] = field(default_factory=list)


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


def get_vm_host_resources(pod):
    """Return used resources for a VM host by its ID."""
    if pod.host is None:
        return []
    vms = list(
        VirtualMachine.objects.annotate(
            system_id=Coalesce("machine__system_id", None)
        )
        .filter(bmc=pod)
        .all()
    )
    numanodes = {
        node.index: node
        for node in NUMANode.objects.prefetch_related("hugepages_set")
        .filter(node=pod.host)
        .all()
    }

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
        numanode_hugepages[numa_idx] = numa_node.hugepages_set.first()

    # map VM IDs to host NUMA nodes indexes
    for vm in vms:
        if not vm.pinned_cores:
            continue
        _update_numanode_resources_usage(
            vm,
            numanodes,
            numanode_hugepages,
            available_numanode_cores,
            allocated_numanode_memory,
            allocated_numanode_hugepages,
            numanode_vms_resources,
        )

    return [
        _get_numa_pinning_resources(
            numa_node,
            available_numanode_cores[numa_idx],
            allocated_numanode_memory[numa_idx],
            numanode_hugepages[numa_idx],
            allocated_numanode_hugepages[numa_idx],
            numanode_vms_resources[numa_idx],
        )
        for numa_idx, numa_node in numanodes.items()
    ]


def _update_numanode_resources_usage(
    vm,
    numanodes,
    numanode_hugepages,
    available_numanode_cores,
    allocated_numanode_memory,
    allocated_numanode_hugepages,
    numanode_vms_resources,
):
    numanode_weights, used_numanode_cores = _get_vm_numanode_weights_and_cores(
        vm, numanodes
    )
    for numa_idx, numa_weight in numanode_weights.items():
        vm_node_memory = int(vm.memory * numa_weight)
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
            numanode_vms_resources[numa_idx].append(
                NUMAPinningVirtualMachineResources(
                    system_id=vm.system_id,
                    pinned_cores=list(used_numanode_cores[numa_idx]),
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
        numa_node.memory - allocated_numanode_memory
    )
    if numanode_hugepages:
        numa_resources.memory.hugepages.append(
            NUMAPinningHugepagesResources(
                page_size=numanode_hugepages.page_size,
                allocated=allocated_numanode_hugepages,
                free=numanode_hugepages.total - allocated_numanode_hugepages,
            )
        )
    numa_resources.vms = numanode_vm_resources
    return numa_resources
