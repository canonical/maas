#  Copyright 2021-2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `VMCluster`.

KVM/VM host support has been removed from MAAS. These endpoints are kept for
backwards compatibility but every operation responds with HTTP 410 Gone.
"""

from maasserver.api.support import OperationsHandler
from maasserver.exceptions import MAASAPIGone

VMHOST_REMOVED_MESSAGE = "VM host (KVM) support has been removed from MAAS."


def _gone(*args, **kwargs):
    raise MAASAPIGone(VMHOST_REMOVED_MESSAGE)


class VmClusterHandler(OperationsHandler):
    """
    Read operations for the VM Cluster object.

    VM host (KVM) support has been removed. This endpoint always returns
    HTTP 410 Gone.
    """

    api_doc_section_name = "Virtual Machine Cluster"
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
    create = update = delete = None
    read = _gone

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("vm_clusters_handler", [])
