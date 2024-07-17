# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import json

from maasserver.api.support import OperationsHandler
from maasserver.models.node import Machine


class SwitchBootOrderHandler(OperationsHandler):
    """Internal endpoint to switch boot order of a machine"""

    api_doc_section_name = "SwitchBootOrder"
    read = create = delete = None
    hidden = True
    fields = ()

    @classmethod
    def resource_uri(cls, node=None):
        node_id = "system_id"
        if node is not None:
            node_id = node.system_id
        return ("switch_boot_order_handler", (node_id,))

    def update(self, request, system_id):
        data = request.data
        machine = Machine.objects.get(system_id=system_id)
        network_boot = data.get("network_boot", False)
        if isinstance(network_boot, str):
            network_boot = json.loads(network_boot.lower())
        machine.set_boot_order(network_boot=network_boot)
