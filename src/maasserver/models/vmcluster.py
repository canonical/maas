# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass, field
from functools import partial
from typing import Dict

from django.core.exceptions import PermissionDenied
from django.db import connection
from django.db.models import (
    ForeignKey,
    Manager,
    PROTECT,
    SET_DEFAULT,
    TextField,
)
from django.shortcuts import get_object_or_404
from twisted.internet.defer import DeferredList, inlineCallbacks, succeed

from maasserver.models.cleansave import CleanSave
from maasserver.models.node import get_default_zone
from maasserver.models.resourcepool import ResourcePool
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.models.zone import Zone
from maasserver.permissions import VMClusterPermission
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.utils.twisted import asynchronous


def _add_vmresources(cluster_resource, host_resource):
    cluster_resource.allocated_tracked += host_resource.allocated_tracked
    cluster_resource.allocated_other += host_resource.allocated_other
    cluster_resource.free += host_resource.free
    cluster_resource.overcommited += host_resource.overcommited
    return cluster_resource


def aggregate_vmhost_resources(cluster_resources, host_resources):
    cluster_resources.vmhost_count += 1
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
                backend=pool.backend,
                path=pool.path,
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
    def group_by_physical_cluster(self, user, perm):
        from maasserver.rbac import rbac

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

        if rbac.is_enabled():
            if perm != VMClusterPermission.view:
                raise ValueError("Unknown perm: %s" % perm)
            result = []
            fetched = rbac.get_resource_pool_ids(
                user.username, "view", "view-all"
            )
            pool_ids = set(fetched["view"] + fetched["view-all"])
            for cluster_group in cluster_groups:
                cluster_group_list = list(
                    self.filter(id__in=cluster_group[0], pool_id__in=pool_ids)
                )
                if cluster_group_list:
                    result.append(cluster_group_list)
            return result
        return [
            list(self.filter(id__in=cluster_group[0]))
            for cluster_group in cluster_groups
        ]

    def get_clusters(self, user, perm):
        from maasserver.rbac import rbac

        if rbac.is_enabled():
            if perm == VMClusterPermission.view:
                fetched = rbac.get_resource_pool_ids(
                    user.username, "view", "view-all"
                )
                pool_ids = set(fetched["view"] + fetched["view-all"])
                return self.filter(pool_id__in=pool_ids)
            else:
                raise ValueError("Unknown perm: %s" % perm)
        return self.all()

    def get_cluster_or_404(self, id, user, perm, **kwargs):
        cluster = get_object_or_404(self, id=id, **kwargs)
        if user.has_perm(perm, cluster):
            return cluster
        else:
            raise PermissionDenied()


class VMCluster(CleanSave, TimestampedModel):
    """Model for a cluster of VM hosts"""

    objects = VMClusterManager()

    name = TextField(unique=True)
    project = TextField()
    pool = ForeignKey(
        ResourcePool,
        default=None,
        null=True,
        blank=True,
        editable=True,
        on_delete=PROTECT,
    )
    zone = ForeignKey(
        Zone,
        verbose_name="Physical zone",
        default=get_default_zone,
        editable=True,
        db_index=True,
        on_delete=SET_DEFAULT,
    )

    def __str__(self):
        return f"VMCluster {self.id} ({self.name})"

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

        cluster_pools = {}
        for h in host_pools:
            for p in h.values():
                if p.name in cluster_pools:
                    cluster_pools[p.name].allocated += p.allocated
                    if not cluster_pools[p.name].shared:
                        cluster_pools[p.name].total += p.total
                else:
                    cluster_pools[p.name] = VMClusterStoragePool(
                        name=p.name,
                        backend=p.backend,
                        path=p.path,
                        allocated=p.allocated,
                        total=p.total,
                    )
        return cluster_pools

    @transactional
    def update_certificate(self, cert, key, skip=None):
        """Update vmcluster certificates"""
        if cert is None or key is None:
            return

        for vmhost in self.hosts():
            if skip is not None and vmhost.id == skip.id:
                continue
            power_parameters = vmhost.power_parameters.copy()
            power_parameters["certificate"] = cert
            power_parameters["key"] = key
            vmhost.power_parameters = power_parameters
            vmhost.save()

    @asynchronous
    def async_update_vmhosts(self, changed_data):
        """Updates cluster's vmhosts"""

        @transactional
        def _get_peers(cluster, updated_attrs):
            peers = [peer for peer in cluster.hosts()]
            updated_data = {
                attr: getattr(cluster, attr) for attr in updated_attrs
            }
            return (peers, updated_data)

        @transactional
        def _update_vmhost(vmhost, updated_data):
            for attr, value in updated_data.items():
                setattr(vmhost, attr, value)
            vmhost.save(update_fields=updated_data.keys())

        @inlineCallbacks
        def _update_peers(result):
            (peers, updated_data) = result
            yield DeferredList(
                [
                    deferToDatabase(_update_vmhost, peer, updated_data)
                    for peer in peers
                ]
            )

        # filter attributes that should not be propagated
        valid_fields = ["zone", "pool"]
        updated_attrs = list(set(valid_fields) & set(changed_data))

        if len(updated_attrs) == 0:
            return succeed(self)

        d = deferToDatabase(_get_peers, self, updated_attrs)
        d.addCallback(_update_peers)
        return d

    @asynchronous
    def async_delete(self, decompose=False):
        """Delete a vmcluster asynchronously.

        If `decompose` is True, any machine in a pod in this cluster will be
        decomposed before it is removed from the database. If there are any
        errors during decomposition, the deletion of the machine and
        ultimately the vmcluster is not stopped.
        """

        @transactional
        def _get_peers(cluster):
            peers = [peer for peer in cluster.hosts()]
            return (cluster.id, peers)

        @inlineCallbacks
        def _delete_cluster_peers(result):
            (cluster_id, peers) = result
            yield DeferredList(
                [
                    peer.async_delete(decompose=decompose, delete_peers=False)
                    for peer in peers
                ]
            )
            return cluster_id

        @transactional
        def _do_delete(cluster_id):
            cluster = VMCluster.objects.get(id=cluster_id)
            cluster.delete()

        d = deferToDatabase(_get_peers, self)
        d.addCallback(_delete_cluster_peers)
        d.addCallback(partial(deferToDatabase, _do_delete))
        return d


@dataclass
class VMClusterResource:
    """VMClusterResource provides tracking of a resource across a cluster of VMs"""

    allocated_tracked: int = 0
    allocated_other: int = 0
    free: int = 0
    overcommited: int = 0

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

    @property
    def total(self):
        return self.tracked - self.other


@dataclass
class VMClusterStoragePool:
    """VMClusterStoragePool tracks the usage of a storage pool accross the cluster"""

    name: str = ""
    path: str = ""
    backend: str = ""
    allocated: int = 0
    total: int = 0

    @property
    def shared(self):
        return self.backend == "ceph"

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
    vmhost_count: int = 0
