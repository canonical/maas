# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass, field

from django.db.models import TextField

from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


def _add_vmresources(cluster_resource, host_resource):
    cluster_resource.allocated_tracked += host_resource.allocated_tracked
    cluster_resource.allocated_other += host_resource.allocated_other
    cluster_resource.free += host_resource.free
    return cluster_resource


def aggregate_vmhost_resources(cluster_resources, host_resources):
    cluster_resources.cores = _add_vmresources(
        cluster_resources.cores, host_resources.cores
    )
    cluster_resources.memory.hugepages = _add_vmresources(
        cluster_resources.memory.hugepages, host_resources.memory.hugepages
    )
    cluster_resources.memory.general = _add_vmresources(
        cluster_resources.memory.general, host_resources.memory.general
    )
    cluster_resources.storage = _add_vmresources(
        cluster_resources.storage, host_resources.storage
    )
    cluster_resources.vm_count.tracked += host_resources.vm_count.tracked
    cluster_resources.vm_count.other += host_resources.vm_count.other


class VMCluster(CleanSave, TimestampedModel):
    """Model for a cluster of VM hosts"""

    name = TextField(unique=True)
    project = TextField()

    def hosts(self):
        from maasserver.models.bmc import Pod

        return Pod.objects.filter(hints__cluster=self.id)

    def total_resources(self):
        from maasserver.models.virtualmachine import get_vm_host_resources

        resources = [get_vm_host_resources(host) for host in self.hosts()]
        if not resources:
            return VMClusterResources()

        cluster_resources = VMClusterResources()
        for resource in resources:
            aggregate_vmhost_resources(cluster_resources, resource)
        return cluster_resources

    def virtual_machines(self):
        from maasserver.models.virtualmachine import VirtualMachine

        hosts = self.hosts()
        return VirtualMachine.objects.filter(bmc__in=hosts)


@dataclass
class VMClusterResource:
    """VMClusterResource provides tracking of a resource across a cluster of VMs"""

    allocated_tracked: int = 0
    allocated_other: int = 0
    free: int = 0

    @property
    def allocated(self):
        return self.allocated_tracked + self.allocated_other


@dataclass
class VMClusterMemoryResource:
    """VMClusterMemoryResource tracks memory resources across a cluster of VMs"""

    hugepages: VMClusterResource = field(default_factory=VMClusterResource)
    general: VMClusterResource = field(default_factory=VMClusterResource)


@dataclass
class VMClusterVMCount:
    """VMClusterVMCount provides the total count of VMs across the cluster"""

    tracked: int = 0
    other: int = 0


@dataclass
class VMClusterResources:
    """Resources for a VM Cluster"""

    cores: VMClusterResource = field(default_factory=VMClusterResource)
    memory: VMClusterMemoryResource = field(
        default_factory=VMClusterMemoryResource
    )
    storage: VMClusterResource = field(default_factory=VMClusterResource)
    vm_count: VMClusterVMCount = field(default_factory=VMClusterVMCount)
