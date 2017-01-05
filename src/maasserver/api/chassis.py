# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

__all__ = [
    "ChassiHandler",
    "ChassisHandler",
    ]

from django.shortcuts import get_object_or_404
from maasserver.api.nodes import (
    NodeHandler,
    NodesHandler,
)
from maasserver.api.support import (
    admin_method,
    operation,
)
from maasserver.enum import NODE_PERMISSION
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms import ChassisForm
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

    # Remove following operations inherited from NodesHandler.
    details = power_parameters = None

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

    @admin_method
    @operation(idempotent=True)
    def chassis_parameters(self, request, system_id):
        """Obtain chassis parameters.

        This method is reserved for admin users and returns a 403 if the
        user is not one.

        This returns the chassis parameters, if any, configured for a
        chassis. For some types of chassis this will include private
        information such as passwords and secret keys.

        Returns 404 if the chassis is not found.
        """
        chassis = get_object_or_404(self.model, system_id=system_id)
        return chassis.power_parameters

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
    update = delete = None
    base_model = Chassis

    # Remove following operations inherited from NodesHandler.
    is_registered = set_zone = None

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('chassis_handler', [])

    @admin_method
    def create(self, request):
        """Create a Chassis.

        :param chassis_type: Type of chassis to create.
        :param hostname: Hostname for the chassis (optional).

        Returns 503 if the chassis could not be discovered.
        Returns 404 if the chassis is not found.
        Returns 403 if the user does not have permission to create a chassis.
        """
        form = ChassisForm(data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)
