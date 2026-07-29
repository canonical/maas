# Copyright 2016-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Pod`.

KVM/VM host support has been removed from MAAS. These endpoints are kept in
order to provide more informative messages for clients that might still try
to call them.
"""

from maasserver.api.gone import vmhost_gone as _gone
from maasserver.api.support import deprecated, operation, OperationsHandler


class VmHostHandler(OperationsHandler):
    """
    Manage an individual VM host.

    VM host (KVM) support has been removed. This endpoint always returns
    HTTP 410 Gone.
    """

    api_doc_section_name = "vm host"
    hidden = True

    create = None
    read = update = delete = _gone

    @operation(idempotent=False)
    def refresh(self, request, id):
        """@description-title Refresh a VM host
        @description VM host support has been removed from MAAS.
        """
        _gone()

    @operation(idempotent=True)
    def parameters(self, request, id):
        """@description-title Obtain VM host parameters
        @description VM host support has been removed from MAAS.
        """
        _gone()

    @operation(idempotent=False)
    def compose(self, request, id):
        """@description-title Compose a virtual machine on the host
        @description VM host support has been removed from MAAS.
        """
        _gone()

    @operation(idempotent=False)
    def add_tag(self, request, id):
        """@description-title Add a tag to a VM host
        @description VM host support has been removed from MAAS.
        """
        _gone()

    @operation(idempotent=False)
    def remove_tag(self, request, id):
        """@description-title Remove a tag from a VM host
        @description VM host support has been removed from MAAS.
        """
        _gone()

    @classmethod
    def resource_uri(cls, pod=None):
        pod_id = pod.id if pod else "id"
        return ("vm_host_handler", (pod_id,))


# Pods are being renamed to VM hosts. Keep the old name on the API as well for
# backwards-compatibility.
@deprecated(use=VmHostHandler)
class PodHandler(VmHostHandler):
    """
    Manage an individual Pod.

    VM host (KVM) support has been removed. This endpoint always returns
    HTTP 410 Gone.
    """

    api_doc_section_name = "Pod"
    hidden = True

    @classmethod
    def resource_uri(cls, pod=None):
        pod_id = pod.id if pod else "id"
        return ("pod_handler", (pod_id,))


class VmHostsHandler(OperationsHandler):
    """
    Manage the collection of all the VM hosts in MAAS.

    VM host (KVM) support has been removed. This endpoint always returns
    HTTP 410 Gone.
    """

    api_doc_section_name = "vm hosts"
    hidden = True
    update = delete = None

    read = create = _gone

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("vm_hosts_handler", [])


# Pods are being renamed to VM hosts. Keep the old name on the API as well for
# backwards-compatibility.
@deprecated(use=VmHostsHandler)
class PodsHandler(VmHostsHandler):
    """
    Manage the collection of all the pods in the MAAS.

    VM host (KVM) support has been removed. This endpoint always returns
    HTTP 410 Gone.
    """

    api_doc_section_name = "Pods"
    hidden = True

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("pods_handler", [])
