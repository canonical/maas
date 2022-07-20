# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `VMCluster`."""

from piston3.utils import rc

from maasserver.api.support import admin_method, OperationsHandler
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms.vmcluster import DeleteVMClusterForm, UpdateVMClusterForm
from maasserver.models import VMCluster
from maasserver.permissions import VMClusterPermission

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
    "storage_pools",
)


class VmClusterHandler(OperationsHandler):
    """
    Read operations for the VM Cluster object

    A VM Cluster is identified by its id
    """

    api_doc_section_name = "Virtual Machine Cluster"
    create = None
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

    @classmethod
    def storage_pools(cls, cluster):
        pools = cluster.storage_pools()
        return {
            n: {
                "free": p.free,
                "total": p.total,
                "allocated_tracked": p.allocated_tracked,
                "allocated_other": p.allocated_other,
                "path": p.path,
                "backend": p.backend,
            }
            for n, p in pools.items()
        }

    @admin_method
    def update(self, request, *args, **kwargs):
        """@description-title Update VMCluster
        @description Update a specific VMCluster by ID.

        @param (url-string) "{id}" [required=true] The VMCluster's ID.
        @param (string) "name" [required=false] The VMCluster's name.
        @param (string) "pool" [required=false] The name of the resource pool
        associated with this VM Cluster -- this change is propagated to VMHosts
        @param (string) "zone" [required=false] The VMCluster's zone.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON VMClister object.
        @success-example "success-json" [exkey=read-vmcluster] placeholder text

        @error (http-status-code) "404" 404 -- The VMCluster's ID was not found.
        @error (http-status-code) "403" 403 -- The current user does not have
        permission to update the VMCluster.

        """
        cluster = VMCluster.objects.get_cluster_or_404(
            kwargs["id"], request.user, VMClusterPermission.edit
        )
        form = UpdateVMClusterForm(
            data=request.data, instance=cluster, request=request
        )
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)
        cluster = form.save()
        cluster.async_update_vmhosts(form.changed_data).wait(60)

        return cluster

    @admin_method
    def delete(self, request, *args, **kwargs):
        """@description-title Deletes a VM cluster
        @description Deletes a VM cluster with the given ID.

        @param (int) "{id}" [required=true] The VM cluster's ID.
        @param (boolean) "decompose" [required=false] Whether to also also
        decompose all machines in the VM cluster on removal. If not provided, machines
        will not be removed.

        @success (http-status-code) "204" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" No VM cluster with that ID can be found.
        @error-example "not-found"
            No VMCluster matches the given query.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have the permissions
        to delete the VM cluster.
        @error-example (content) "no-perms"
            This method is reserved for admin users.

        """
        cluster = VMCluster.objects.get_cluster_or_404(
            kwargs["id"], request.user, VMClusterPermission.delete
        )
        form = DeleteVMClusterForm(data=request.GET)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)

        machine_wait = 60
        decompose = form.cleaned_data["decompose"]
        if decompose:
            machine_wait += len(cluster.hosts()) * 60

        cluster.async_delete(decompose=decompose).wait(machine_wait)
        return rc.DELETED


class VmClustersHandler(OperationsHandler):
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
        return VMCluster.objects.get_clusters(
            request.user, VMClusterPermission.view
        ).order_by("id")
