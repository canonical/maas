# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass, field
from typing import Dict

from django.db import connection
from django.db.models import Manager, TextField

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
    cluster_resources.vm_count.tracked += host_resources.vm_count.tracked
    cluster_resources.vm_count.other += host_resources.vm_count.other

    cluster_resources.storage.allocated_tracked += (
        host_resources.storage.allocated_tracked
    )
    cluster_resources.storage.allocated_other += (
        host_resources.storage.allocated_other
    )

    added_storage = 0
    for pool in host_resources.storage_pools.values():
        if pool.name in cluster_resources.storage_pools:
            cluster_resources.storage_pools[
                pool.name
            ].allocated += pool.allocated
            if not pool.shared:
                cluster_resources.storage_pools[pool.name].total += pool.total
                added_storage += pool.total

        else:
            cluster_resources.storage_pools[pool.name] = VMClusterStoragePool(
                name=pool.name,
                shared=pool.shared,
                allocated=pool.allocated,
                total=pool.total,
            )
            added_storage += pool.total

    cluster_resources.storage.free += (
        added_storage
        - host_resources.storage.allocated_tracked
        - host_resources.storage.allocated_other
    )


class VMClusterManager(Manager):
    def group_by_physical_cluster(self):
        cursor = connection.cursor()

        # find all unique power addresses with a cluster relation,
        # aggregate each cluster id of said address into an array
        query = """
        SELECT DISTINCT clusters.cluster FROM (
            SELECT
                array_agg(DISTINCT cluster.id) as cluster,
                bmc.power_parameters->>'power_address' as power_address
            FROM maasserver_vmcluster cluster, maasserver_podhints hints, maasserver_bmc bmc
            WHERE hints.pod_id=bmc.id AND hints.cluster_id=cluster.id AND hints.cluster_id IS NOT NULL
            GROUP BY bmc.power_parameters->>'power_address'
        ) as clusters GROUP BY clusters.cluster;
        """
        cursor.execute(query)
        cluster_groups = cursor.fetchall()
        return [
            list(self.filter(id__in=cluster_group[0]))
            for cluster_group in cluster_groups
        ]


class VMCluster(CleanSave, TimestampedModel):
    """Model for a cluster of VM hosts"""

    objects = VMClusterManager()

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

    def storage_pools(self):
        from maasserver.models.virtualmachine import get_vm_host_storage_pools

        host_pools = [get_vm_host_storage_pools(host) for host in self.hosts()]

        cluster_pools = dict()
        for h in host_pools:
            for p in h.values():
                if p.name in cluster_pools:
                    cluster_pools[p.name].allocated += p.allocated
                    if not cluster_pools[p.name].shared:
                        cluster_pools[p.name].total += p.total
                else:
                    cluster_pools[p.name] = VMClusterStoragePool(
                        name=p.name,
                        shared=p.shared,
                        allocated=p.allocated,
                        total=p.total,
                    )
        return cluster_pools


@dataclass
class VMClusterResource:
    """VMClusterResource provides tracking of a resource across a cluster of VMs"""

    allocated_tracked: int = 0
    allocated_other: int = 0
    free: int = 0

    @property
    def allocated(self):
        return self.allocated_tracked + self.allocated_other

    @property
    def total(self):
        return self.allocated + self.free


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
class VMClusterStoragePool:
    """VMClusterStoragePool tracks the usage of a storage pool accross the cluster"""

    name: str = ""
    shared: bool = False
    allocated: int = 0
    total: int = 0

    @property
    def free(self):
        return self.total - self.allocated


@dataclass
class VMClusterResources:
    """Resources for a VM Cluster"""

    cores: VMClusterResource = field(default_factory=VMClusterResource)
    memory: VMClusterMemoryResource = field(
        default_factory=VMClusterMemoryResource
    )
    storage: VMClusterResource = field(default_factory=VMClusterResource)
    storage_pools: Dict[str, VMClusterStoragePool] = field(
        default_factory=dict
    )
    vm_count: VMClusterVMCount = field(default_factory=VMClusterVMCount)
