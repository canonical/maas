# Copyright 2021-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `VMCluster`.

KVM/VM host support has been removed from MAAS. These endpoints are kept in
order to provide more informative messages for clients that might still try
to call them.
"""

from maasserver.api.gone import vmhost_gone as _gone
from maasserver.api.support import OperationsHandler


class VmClusterHandler(OperationsHandler):
    """
    Read operations for the VM Cluster object.

    VM host (KVM) support has been removed. This endpoint always returns
    HTTP 410 Gone.
    """

    api_doc_section_name = "Virtual Machine Cluster"
    hidden = True
    create = None
    read = update = delete = _gone

    @classmethod
    def resource_uri(cls, cluster=None):
        cluster_id = cluster.id if cluster else "id"
        return ("vm_cluster_handler", (cluster_id,))


class VmClustersHandler(OperationsHandler):
    """
    Read operations for the collection of VM Clusters.

    VM host (KVM) support has been removed. This endpoint always returns
    HTTP 410 Gone.
    """

    api_doc_section_name = "Virtual Machine Clusters"
    hidden = True
    create = update = delete = None
    read = _gone

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("vm_clusters_handler", [])
