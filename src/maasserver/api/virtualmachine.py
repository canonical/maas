#  Copyright 2020-2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `VirtualMachine`.

KVM/VM host support has been removed from MAAS. These endpoints are kept for
backwards compatibility but every operation responds with HTTP 410 Gone.
"""

from maasserver.api.support import OperationsHandler
from maasserver.exceptions import MAASAPIGone

VMHOST_REMOVED_MESSAGE = "VM host (KVM) support has been removed from MAAS."


def _gone(*args, **kwargs):
    raise MAASAPIGone(VMHOST_REMOVED_MESSAGE)


class VirtualMachineHandler(OperationsHandler):
    """Manage individual virtual machines.

    VM host (KVM) support has been removed. This endpoint always returns
    HTTP 410 Gone.
    """

    api_doc_section_name = "Virtual Machine"
    hidden = True

    create = update = delete = None
    read = _gone

    @classmethod
    def resource_uri(cls, machine=None):
        machine_id = machine.id if machine else "id"
        return ("virtual_machine_handler", (machine_id,))


class VirtualMachinesHandler(OperationsHandler):
    """Manage a collection of virtual machines.

    VM host (KVM) support has been removed. This endpoint always returns
    HTTP 410 Gone.
    """

    api_doc_section_name = "Virtual Machines"
    hidden = True

    create = update = delete = None
    read = _gone

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("virtual_machines_handler", [])
