# Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

__all__ = [
    'RegionControllerHandler',
    'RegionControllersHandler',
    ]

from maasserver.api.interfaces import DISPLAYED_INTERFACE_FIELDS
from maasserver.api.nodes import (
    NodeHandler,
    NodesHandler,
)
from maasserver.api.support import admin_method
from maasserver.enum import NODE_PERMISSION
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms import ControllerForm
from maasserver.models import RegionController

# Region controller's fields exposed on the API.
DISPLAYED_REGION_CONTROLLER_FIELDS = (
    'system_id',
    'hostname',
    'domain',
    'fqdn',
    'architecture',
    'cpu_count',
    'cpu_speed',
    'memory',
    'swap_size',
    'osystem',
    'distro_series',
    'power_type',
    'power_state',
    'ip_addresses',
    ('interface_set', DISPLAYED_INTERFACE_FIELDS),
    'zone',
    'status_action',
    'node_type',
    'node_type_name',
    'current_commissioning_result_id',
    'current_testing_result_id',
    'current_installation_result_id',
    'version',
    'commissioning_status',
    'commissioning_status_name',
    'testing_status',
    'testing_status_name',
    'cpu_test_status',
    'cpu_test_status_name',
    'memory_test_status',
    'memory_test_status_name',
    'storage_test_status',
    'storage_test_status_name',
    'other_test_status',
    'other_test_status_name',
    'hardware_info',
)


class RegionControllerHandler(NodeHandler):
    """Manage an individual region controller.

    The region controller is identified by its system_id.
    """
    api_doc_section_name = "RegionController"
    model = RegionController
    fields = DISPLAYED_REGION_CONTROLLER_FIELDS

    @admin_method
    def update(self, request, system_id):
        """Update a specific Region controller.

        :param power_type: The new power type for this region controller. If
            you use the default value, power_parameters will be set to the
            empty string.
            Available to admin users.
            See the `Power types`_ section for a list of the available power
            types.
        :type power_type: unicode

        :param power_parameters_{param1}: The new value for the 'param1'
            power parameter.  Note that this is dynamic as the available
            parameters depend on the selected value of the region controller's
            power_type.  Available to admin users. See the `Power types`_
            section for a list of the available power parameters for each
            power type.
        :type power_parameters_{param1}: unicode

        :param power_parameters_skip_check: Whether or not the new power
            parameters for this region controller should be checked against the
            expected power parameters for the region controller's power type
            ('true' or 'false').
            The default is 'false'.
        :type power_parameters_skip_check: unicode

        :param zone: Name of a valid physical zone in which to place this
            region controller.
        :type zone: unicode

        Returns 404 if the region controller is not found.
        Returns 403 if the user does not have permission to update the region
        controller.
        """
        region = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NODE_PERMISSION.EDIT)
        form = ControllerForm(data=request.data, instance=region)

        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    @classmethod
    def resource_uri(cls, regioncontroller=None):
        regioncontroller_id = "system_id"
        if regioncontroller is not None:
            regioncontroller_id = regioncontroller.system_id
        return ('regioncontroller_handler', (regioncontroller_id, ))


class RegionControllersHandler(NodesHandler):
    """Manage the collection of all region controllers in MAAS."""
    api_doc_section_name = "RegionControllers"
    base_model = RegionController

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('regioncontrollers_handler', [])
