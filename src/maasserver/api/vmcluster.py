# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `VMCluster`."""


from maasserver.api.support import OperationsHandler
from maasserver.models import VMCluster

DISPLAYED_VMCLUSTER_FIELDS = (
    "id",
    "name",
    "project",
    "vmhost_count",
    "vm_count",
    "version",
    "total",
    "used",
    "available",
)


class VMClusterHandler(OperationsHandler):
    """
    Read operations for the VM Cluster object

    A VM Cluster is identified by its id
    """

    api_doc_section_name = "Virtual Machine Cluster"
    create = update = delete = None
    model = VMCluster
    fields = DISPLAYED_VMCLUSTER_FIELDS

    @classmethod
    def resource_uri(cls, cluster=None):
        cluster_id = cluster.id if cluster else "id"
        return ("vm_cluster_handler", (cluster_id,))

    @classmethod
    def vmhost_count(cls, cluster):
        return len(cluster.hosts())

    @classmethod
    def vm_count(cls, cluster):
        return cluster.total_resources().vm_count.tracked

    @classmethod
    def version(cls, cluster):
        hosts = cluster.hosts()
        if hosts:
            return hosts[0].version
        return ""

    @classmethod
    def total(cls, cluster):
        resources = cluster.total_resources()
        return {
            "cores": resources.cores.total,
            "memory": resources.memory.general.total,
            "local_storage": resources.storage.total,
        }

    @classmethod
    def used(cls, cluster):
        resources = cluster.total_resources()
        return {
            "cores": resources.cores.allocated,
            "memory": resources.memory.general.allocated,
            "local_storage": resources.storage.allocated,
        }

    @classmethod
    def available(cls, cluster):
        resources = cluster.total_resources()
        return {
            "cores": resources.cores.free,
            "memory": resources.memory.general.free,
            "local_storage": resources.storage.free,
        }


class VMClustersHandler(OperationsHandler):
    """
    Read operations for the VM Clusters collection
    """

    api_doc_section_name = "Virtual Machine Clusters"
    create = update = delete = None

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("vm_clusters_handler", [])

    def read(self, request):
        """@description-title List VM Clusters
        @description Get a listing of all VM Clusters

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing a list of
        VM Cluster objects.
        @success-example (json) "success-json" [exkey=read-vmclusters]
        placeholder text
        """
        return VMCluster.objects.order_by("id")
