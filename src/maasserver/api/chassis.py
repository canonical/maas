# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

__all__ = [
    "ChassiHandler",
    "ChassisHandler",
    ]

from maasserver.api.nodes import (
    NodeHandler,
    NodesHandler,
)
from maasserver.enum import NODE_PERMISSION
from maasserver.models.node import Chassis
from piston3.utils import rc

# Chassis fields exposed on the API.
DISPLAYED_CHASSIS_FIELDS = (
    'system_id',
    'hostname',
    'cpu_count',
    'memory',
    'chassis_type',
    'node_type',
    'node_type_name',
    )


class ChassiHandler(NodeHandler):
    """Manage an individual chassis.

    The chassis is identified by its system_id.
    """
    api_doc_section_name = "Chassis"

    create = update = None
    model = Chassis
    fields = DISPLAYED_CHASSIS_FIELDS

    @classmethod
    def chassis_type(cls, chassis):
        return chassis.power_type

    def delete(self, request, system_id):
        """Delete a specific Chassis.

        Returns 404 if the chassis is not found.
        Returns 403 if the user does not have permission to delete the chassis.
        Returns 204 if the chassis is successfully deleted.
        """
        chassis = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user,
            perm=NODE_PERMISSION.ADMIN)
        chassis.delete()
        return rc.DELETED

    @classmethod
    def resource_uri(cls, chassis=None):
        # This method is called by piston in two different contexts:
        # - when generating an uri template to be used in the documentation
        # (in this case, it is called with node=None).
        # - when populating the 'resource_uri' field of an object
        # returned by the API (in this case, node is a node object).
        chassis_system_id = "system_id"
        if chassis is not None:
            chassis_system_id = chassis.system_id
        return ('chassi_handler', (chassis_system_id,))


class ChassisHandler(NodesHandler):
    """Manage the collection of all the chassis in the MAAS."""
    api_doc_section_name = "Chassis"
    create = update = delete = None
    base_model = Chassis

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('chassis_handler', [])
