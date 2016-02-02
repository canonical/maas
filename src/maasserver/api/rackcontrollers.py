# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

__all__ = [
    'RackControllerHandler',
    'RackControllersHandler',
    ]

from maasserver.api.nodes import (
    NodeHandler,
    NodesHandler,
)
from maasserver.api.support import (
    admin_method,
    operation,
)
from maasserver.enum import NODE_PERMISSION
from maasserver.models import RackController


class RackControllerHandler(NodeHandler):
    """Manage an individual rack controller.

    The rack controller is identified by its system_id.
    """
    api_doc_section_name = "RackController"
    model = RackController

    @admin_method
    @operation(idempotent=False)
    def refresh(self, request, system_id):
        """Refresh the hardware information for a specific rack controller.

        Returns 404 if the node is not found.
        Returns 403 if the user does not have permission to refresh the rack.
        """
        rack = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NODE_PERMISSION.EDIT)
        rack.refresh()
        return None

    @classmethod
    def resource_uri(cls, rackcontroller=None):
        rackcontroller_id = "system_id"
        if rackcontroller is not None:
            rackcontroller_id = rackcontroller.system_id
        return ('rackcontroller_handler', (rackcontroller_id, ))


class RackControllersHandler(NodesHandler):
    """Manage the collection of all rack controllers in MAAS."""
    api_doc_section_name = "RackControllers"
    base_model = RackController

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('rackcontrollers_handler', [])
