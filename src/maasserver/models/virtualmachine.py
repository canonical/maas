# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from collections import defaultdict, OrderedDict
from dataclasses import dataclass, field, InitVar
from math import ceil
from typing import Dict, List, Optional

from django.contrib.postgres.aggregates import ArrayAgg
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db.models import (
    BigIntegerField,
    BooleanField,
    CASCADE,
    CharField,
    Count,
    ExpressionWrapper,
    F,
    ForeignKey,
    IntegerField,
    Manager,
    OneToOneField,
    Q,
    SET_NULL,
    Sum,
    TextField,
    Value,
)
from django.db.models.constraints import UniqueConstraint
from django.db.models.functions import Coalesce

from maasserver.fields import MACAddressField
from maasserver.models.blockdevice import BlockDevice
from maasserver.models.bmc import BMC
from maasserver.models.cleansave import CleanSave
from maasserver.models.interface import Interface
from maasserver.models.node import Machine
from maasserver.models.numa import NUMANode
from maasserver.models.podstoragepool import PodStoragePool
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.orm import ArrayLength, NotNullSum
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
        on_delete=SET_NULL,
        default=None,
        blank=True,
        null=True,
        related_name="virtualmachine",
    )
    project = TextField(default="", blank=True)
    bmc = ForeignKey(BMC, on_delete=CASCADE)

    class Meta:
        unique_together = [("bmc", "identifier", "project")]

    def clean(self):
        super().clean()
        if self.pinned_cores and self.unpinned_cores:
            raise ValidationError(
                "VirtualMachine can't have both pinned and unpinned cores"
            )


class VirtualMachineInterfaceCurrentConfigManager(Manager):
    """Manager filtering VirtualMachineInterface objects by related interfaces.

    This only returns entries that are either not tied to host interfaces, or
    tied to host interfacse for the related machine current NodeConfig.
    """

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(
                Q(host_interface__isnull=True)
                | Q(
                    host_interface__node_config=F(
                        "host_interface__node_config__node__current_config"
                    )
                )
            )
        )


class VirtualMachineInterface(CleanSave, TimestampedModel):
    """A NIC inside VM that's connected to the host interface."""

    objects = Manager()
    objects_current_config = VirtualMachineInterfaceCurrentConfigManager()

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=("vm", "mac_address"),
                condition=Q(host_interface__isnull=True),
                name="maasserver_virtualmachineinterface_no_iface_uniq",
            ),
            UniqueConstraint(
                fields=("vm", "mac_address", "host_interface"),
                condition=Q(host_interface__isnull=False),
                name="maasserver_virtualmachineinterface_iface_uniq",
            ),
        ]

    vm = ForeignKey(
        VirtualMachine,
        on_delete=CASCADE,
        related_name="+",
    )
    mac_address = MACAddressField(null=True, blank=True)
    host_interface = ForeignKey(Interface, null=True, on_delete=SET_NULL)
    attachment_type = CharField(
        max_length=10,
        null=False,
        choices=InterfaceAttachTypeChoices,
    )


class VirtualMachineDiskCurrentConfigManager(Manager):
    """Manager filtering VirtualMachineDisk objects by related block device.

    This only returns entries that are either not tied to block devices, or
    tied to block devices for the related machine current NodeConfig.
    """

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(
                Q(block_device__isnull=True)
                | Q(block_device__node_config=F("vm__machine__current_config"))
            )
        )


class VirtualMachineDisk(CleanSave, TimestampedModel):
    """A disk attached to a virtual machine."""

    objects = Manager()
    objects_current_config = VirtualMachineDiskCurrentConfigManager()

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=("vm", "name"),
                condition=Q(block_device__isnull=True),
                name="maasserver_virtualmachinedisk_no_bdev_uniq",
            ),
            UniqueConstraint(
                fields=("vm", "name", "block_device"),
                condition=Q(block_device__isnull=False),
                name="maasserver_virtualmachinedisk_bdev_uniq",
            ),
        ]

    name = CharField(max_length=255, blank=False)
    vm = ForeignKey(
        VirtualMachine,
        on_delete=CASCADE,
        related_name="+",
    )
    backing_pool = ForeignKey(
        PodStoragePool,
        null=True,
        on_delete=CASCADE,
        related_name="+",
    )
    block_device = OneToOneField(
        BlockDevice,
        on_delete=SET_NULL,
        blank=True,
        null=True,
        related_name="vmdisk",
    )
    size = BigIntegerField()


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
class NUMAPinningNodeResources:
    """Resource usage for a NUMA node."""

    node_id: int
    memory: NUMAPinningMemoryResources = field(
        default_factory=NUMAPinningMemoryResources
    )
    cores: NUMAPinningCoresResources = field(
        default_factory=NUMAPinningCoresResources
    )
    vms: List[int] = field(default_factory=list)
    interfaces: List[int] = field(default_factory=list)


@dataclass
class VMHostResource:
    """Usage for a resource type in a VM host."""

    allocated_tracked: int = 0
    allocated_other: int = 0
    free: int = 0
    overcommit_ratio: InitVar[float] = 1.0

    @property
    def allocated(self):
        return self.allocated_tracked + self.allocated_other

    @property
    def total(self):
        return self.allocated + self.free

    @property
    def overcommited(self):
        return int(self.total * self.overcommit_ratio)


@dataclass
class VMHostCount:
    """Count a resources for a VM host."""

    tracked: int = 0
    other: int = 0

    @property
    def total(self):
        return self.tracked + self.other


@dataclass
class VMHostMemoryResources:
    """Memory usage details for a VM host."""

    hugepages: VMHostResource = field(default_factory=VMHostResource)
    general: VMHostResource = field(default_factory=VMHostResource)


@dataclass
class VMHostNetworkInterface:
    """Network interface details for a VM host."""

    id: int
    name: str
    numa_index: int
    virtual_functions: VMHostResource = field(default_factory=VMHostResource)


@dataclass
class VMHostVirtualMachineResources:
    """Resource usage for a virtual machine on a VM host."""

    id: int
    system_id: Optional[str]
    memory: int
    hugepages_backed: bool
    unpinned_cores: int
    pinned_cores: List[int]


@dataclass
class VMHostStoragePool:
    """Storage pool available on a VM host"""

    id: str = ""
    name: str = ""
    path: str = ""
    backend: str = ""
    allocated_tracked: int = 0
    allocated_other: int = 0
    total: int = 0

    @property
    def shared(self):
        return self.backend == "ceph"

    @property
    def allocated(self):
        return self.allocated_other + self.allocated_tracked

    @property
    def free(self):
        return self.total - self.allocated


@dataclass
class VMHostResources:
    """Resources for a VM host."""

    cores: VMHostResource = field(default_factory=VMHostResource)
    memory: VMHostMemoryResources = field(
        default_factory=VMHostMemoryResources
    )
    storage: VMHostResource = field(default_factory=VMHostResource)
    storage_pools: Dict[str, VMHostStoragePool] = field(default_factory=dict)
    vm_count: VMHostCount = field(default_factory=VMHostCount)
    interfaces: List[VMHostNetworkInterface] = field(default_factory=list)
    vms: List[VMHostVirtualMachineResources] = field(default_factory=list)
    numa: List[NUMAPinningNodeResources] = field(default_factory=list)


@dataclass
class VMHostUsedResources:
    cores: int
    memory: int
    hugepages_memory: int
    storage: int

    @property
    def total_memory(self):
        """Total used memory"""
        return self.memory + self.hugepages_memory


def get_vm_host_used_resources(vmhost) -> VMHostUsedResources:
    """Return used resources for a VM host."""

    def C(field):
        return Coalesce(field, Value(0))

    counts = VirtualMachine.objects.filter(
        bmc=vmhost, project=vmhost.tracked_project
    ).aggregate(
        cores=C(Sum(F("unpinned_cores") + ArrayLength("pinned_cores"))),
        memory=C(Sum("memory", filter=Q(hugepages_backed=False))),
        hugepages_memory=C(Sum("memory", filter=Q(hugepages_backed=True))),
    )
    counts.update(
        VirtualMachineDisk.objects_current_config.filter(
            vm__bmc=vmhost, vm__project=vmhost.tracked_project
        ).aggregate(
            storage=C(Sum("size")),
        )
    )
    return VMHostUsedResources(**counts)


def get_vm_host_resources(pod, detailed=True) -> VMHostResources:
    """Return used resources for a VM host by its ID.

    If `detailed` is true, also include info about NUMA nodes resource usage.
    """
    resources = _get_global_vm_host_resources(pod)
    if detailed:
        _update_detailed_resource_counters(pod, resources)
    return resources


def get_vm_host_storage_pools(pod) -> Dict[str, VMHostStoragePool]:
    """Return storage pools for a VM host by its ID."""
    resources = _get_global_vm_host_storage(pod, VMHostResources())
    return resources.storage_pools


def _update_detailed_resource_counters(pod, resources):
    numanodes = OrderedDict(
        (node.index, node)
        for node in NUMANode.objects.prefetch_related("hugepages_set")
        .filter(node=pod.host)
        .order_by("index")
        .all()
    )
    # to track how many cores are not used by pinned VMs in each NUMA node
    available_numanode_cores = {}
    # to track how much general memory is allocated in each NUMA node
    allocated_numanode_memory = defaultdict(int)
    # XXX map NUMA nodes to default hugepages entry, since currently LXD only support one size
    numanode_hugepages = {}
    # map NUMA nodes to list of VM IDs
    numanode_vms = defaultdict(list)
    allocated_numanode_hugepages = defaultdict(int)
    for numa_idx, numa_node in numanodes.items():
        available_numanode_cores[numa_idx] = set(numa_node.cores)
        hugepages = numa_node.hugepages_set.first()
        numanode_hugepages[numa_idx] = hugepages

    # only consider VMs in the tracked projects
    vms = list(
        VirtualMachine.objects.annotate(
            system_id=Coalesce("machine__system_id", None)
        )
        .filter(bmc=pod, project=pod.tracked_project)
        .all()
    )

    numanode_interfaces = defaultdict(list)
    for interface in resources.interfaces:
        numanode_interfaces[interface.numa_index].append(interface.id)

    # map VM IDs to NUMA node indexes for VM host interfaces their interfaces
    # are attached to
    vm_ifs_numa_indexes = defaultdict(
        list,
        VirtualMachineInterface.objects_current_config.filter(
            vm__in=vms, host_interface__isnull=False
        )
        .values_list("vm_id")
        .annotate(numa_indexes=ArrayAgg("host_interface__numa_node__index")),
    )

    for vm in vms:
        resources.vms.append(
            VMHostVirtualMachineResources(
                id=vm.id,
                system_id=vm.system_id,
                memory=vm.memory * MB,
                hugepages_backed=vm.hugepages_backed,
                unpinned_cores=vm.unpinned_cores,
                pinned_cores=vm.pinned_cores,
            )
        )
        _update_numanode_resources_usage(
            vm,
            vm_ifs_numa_indexes[vm.id],
            numanodes,
            numanode_hugepages,
            available_numanode_cores,
            allocated_numanode_memory,
            allocated_numanode_hugepages,
            numanode_vms,
        )
    resources.numa = [
        _get_numa_pinning_resources(
            numa_node,
            available_numanode_cores[numa_idx],
            allocated_numanode_memory[numa_idx],
            numanode_hugepages[numa_idx],
            allocated_numanode_hugepages[numa_idx],
            numanode_vms[numa_idx],
            numanode_interfaces[numa_idx],
        )
        for numa_idx, numa_node in numanodes.items()
    ]
    return resources


def _get_global_vm_host_storage(pod, resources):
    """Get VMHost storage details, including storage pools"""
    storage = (
        VirtualMachineDisk.objects_current_config.filter(
            backing_pool__pod=pod,
        )
        .values(
            "backing_pool__name",
            tracked_project=ExpressionWrapper(
                Q(vm__project=pod.tracked_project),
                output_field=BooleanField(),
            ),
        )
        .annotate(
            used=Sum("size"),
        )
    )
    storage_pools = PodStoragePool.objects.filter(
        pod=pod,
    )

    total_storage = 0
    for pool in storage_pools:
        resources.storage_pools[pool.name] = VMHostStoragePool(
            id=pool.pool_id,
            name=pool.name,
            path=pool.path,
            backend=pool.pool_type,
            total=pool.storage,
        )
        total_storage += pool.storage

    for entry in storage:
        pool_name = entry["backing_pool__name"]
        used = entry["used"]

        if entry["tracked_project"]:
            resources.storage.allocated_tracked += used
            if pool_name in resources.storage_pools:
                resources.storage_pools[pool_name].allocated_tracked += used
        else:
            resources.storage.allocated_other += used
            if pool_name in resources.storage_pools:
                resources.storage_pools[pool_name].allocated_other += used

    resources.storage.free = total_storage - resources.storage.allocated
    return resources


def _get_global_vm_host_resources(pod):
    resources = VMHostResources()

    if pod.host:
        totals = NUMANode.objects.filter(node=pod.host).aggregate(
            cores=Sum(ArrayLength("cores")),
            memory=Sum("memory") * MB,
            hugepages=NotNullSum("hugepages_set__total"),
        )
    else:
        # for VM hosts where there is no known machines backing it, info about
        # hardware configuration and NUMA nodes is now known. In this case,
        # fallback to what we know from the Pod object itself.
        totals = {
            "cores": pod.cores,
            "memory": pod.memory * MB,
            "hugepages": 0,  # no info about hugepages configuration
        }

    resources = _get_global_vm_host_storage(pod, resources)

    vms = (
        VirtualMachine.objects.filter(bmc=pod)
        .values("hugepages_backed")
        .annotate(
            tracked=ExpressionWrapper(
                Q(project=pod.tracked_project),
                output_field=BooleanField(),
            ),
            vms=Count("id"),
            cores=Sum(F("unpinned_cores") + ArrayLength("pinned_cores")),
            memory=Sum("memory") * MB,
        )
    )
    for entry in vms:
        mem = entry["memory"]
        if entry["tracked"]:
            resources.cores.allocated_tracked += entry["cores"]
            resources.vm_count.tracked += entry["vms"]
            if entry["hugepages_backed"]:
                resources.memory.hugepages.allocated_tracked += mem
            else:
                resources.memory.general.allocated_tracked += mem
        else:
            resources.cores.allocated_other += entry["cores"]
            resources.vm_count.other += entry["vms"]
            if entry["hugepages_backed"]:
                resources.memory.hugepages.allocated_other += mem
            else:
                resources.memory.general.allocated_other += mem

    resources.cores.free = totals["cores"] - resources.cores.allocated
    resources.cores.overcommit_ratio = pod.cpu_over_commit_ratio
    resources.memory.general.free = (
        totals["memory"] - resources.memory.general.allocated
    )
    resources.memory.general.overcommit_ratio = pod.memory_over_commit_ratio
    resources.memory.hugepages.free = (
        totals["hugepages"] - resources.memory.hugepages.allocated
    )

    host_interfaces = {}
    if pod.host:
        interfaces = (
            Interface.objects.filter(node_config=pod.host.current_config)
            .values("id", "name", "sriov_max_vf")
            .annotate(
                numa_index=F("numa_node__index"),
                allocated=Count("virtualmachineinterface"),
                tracked=ExpressionWrapper(
                    Q(
                        virtualmachineinterface__vm__project=pod.tracked_project
                    ),
                    output_field=BooleanField(),
                ),
                sriov_attached=ExpressionWrapper(
                    Q(
                        virtualmachineinterface__attachment_type=InterfaceAttachType.SRIOV
                    ),
                    output_field=BooleanField(),
                ),
            )
        )
        for entry in interfaces:
            interface = host_interfaces.get(entry["id"])
            if not interface:
                interface = VMHostNetworkInterface(
                    id=entry["id"],
                    name=entry["name"],
                    numa_index=entry["numa_index"],
                    virtual_functions=VMHostResource(
                        free=entry["sriov_max_vf"]
                    ),
                )
                host_interfaces[entry["id"]] = interface
            if not entry["sriov_attached"]:
                continue
            vfs = interface.virtual_functions
            allocated = entry["allocated"]
            if entry["tracked"]:
                vfs.allocated_tracked += allocated
            else:
                vfs.allocated_other += allocated
            vfs.free -= allocated
    resources.interfaces = list(host_interfaces.values())

    return resources


def _update_numanode_resources_usage(
    vm,
    vm_ifs_numa_indexes,
    numanodes,
    numanode_hugepages,
    available_numanode_cores,
    allocated_numanode_memory,
    allocated_numanode_hugepages,
    numanode_vms,
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
        if used_numanode_cores[numa_idx] or numa_idx in vm_ifs_numa_indexes:
            numanode_vms[numa_idx].append(vm.id)


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
    numanode_vms,
    numanode_interfaces,
):
    numa_resources = NUMAPinningNodeResources(
        node_id=numa_node.index,
        vms=numanode_vms,
        interfaces=numanode_interfaces,
    )
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
    return numa_resources
