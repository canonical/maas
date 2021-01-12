# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from maasserver.api.support import (
    ModelCollectionOperationsHandler,
    ModelOperationsHandler,
)
from maasserver.models.virtualmachine import VirtualMachine

DISPLAYED_VM_FIELDS = (
    "id",
    "identifier",
    "project",
    "pinned_cores",
    "unpinned_cores",
    "memory",
    "hugepages_backed",
    "machine_id",
    "bmc_id",
)


class VirtualMachineHandler(ModelOperationsHandler):
    """Manage individual virtual machines.

    A virtual machine is identified by its id.

    """

    api_doc_section_name = "Virtual Machine"

    update = delete = None
    model = VirtualMachine
    fields = DISPLAYED_VM_FIELDS
    handler_url_name = "virtual_machine_handler"


class VirtualMachinesHandler(ModelCollectionOperationsHandler):
    """Manage a collection of virtual machines.

    A virtual machine is identified by its id.

    """

    api_doc_section_name = "Virtual Machines"

    model_manager = VirtualMachine.objects
    handler_url_name = "virtual_machines_handler"
    order_field = "id"
