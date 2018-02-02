# Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

__all__ = [
    'RackControllerHandler',
    'RackControllersHandler',
    ]


from django.conf import settings
from django.http import HttpResponse
from maasserver.api.interfaces import DISPLAYED_INTERFACE_FIELDS
from maasserver.api.nodes import (
    NodeHandler,
    NodesHandler,
    PowerMixin,
    PowersMixin,
)
from maasserver.api.support import (
    admin_method,
    operation,
)
from maasserver.clusterrpc.driver_parameters import (
    get_all_power_types_from_racks,
)
from maasserver.enum import NODE_PERMISSION
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms import ControllerForm
from maasserver.models import RackController
from maasserver.utils.orm import post_commit_do

# Rack controller's fields exposed on the API.
DISPLAYED_RACK_CONTROLLER_FIELDS = (
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
    ('service_set', (
        'name',
        'status',
        'status_info',
        )),
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


class RackControllerHandler(NodeHandler, PowerMixin):
    """Manage an individual rack controller.

    The rack controller is identified by its system_id.
    """
    api_doc_section_name = "RackController"
    model = RackController
    fields = DISPLAYED_RACK_CONTROLLER_FIELDS

    @admin_method
    def update(self, request, system_id):
        """Update a specific Rack controller.

        :param power_type: The new power type for this rack controller. If you
            use the default value, power_parameters will be set to the empty
            string.
            Available to admin users.
            See the `Power types`_ section for a list of the available power
            types.
        :type power_type: unicode

        :param power_parameters_{param1}: The new value for the 'param1'
            power parameter.  Note that this is dynamic as the available
            parameters depend on the selected value of the rack controller's
            power_type.  Available to admin users. See the `Power types`_
            section for a list of the available power parameters for each
            power type.
        :type power_parameters_{param1}: unicode

        :param power_parameters_skip_check: Whether or not the new power
            parameters for this rack controller should be checked against the
            expected power parameters for the rack controller's power type
            ('true' or 'false'). The default is 'false'.
        :type power_parameters_skip_check: unicode

        :param zone: Name of a valid physical zone in which to place this
            rack controller.
        :type zone: unicode

        Returns 404 if the rack controller is not found.
        Returns 403 if the user does not have permission to update the rack
        controller.
        """
        rack = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NODE_PERMISSION.EDIT)
        form = ControllerForm(data=request.data, instance=rack)

        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    @admin_method
    @operation(idempotent=False)
    def import_boot_images(self, request, system_id):
        """Import the boot images on this rack controller.

        Returns 404 if the rack controller is not found.
        """
        # Avoid circular import.
        from maasserver.clusterrpc.boot_images import RackControllersImporter

        rack = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NODE_PERMISSION.EDIT)
        post_commit_do(RackControllersImporter.schedule, rack.system_id)
        return HttpResponse(
            "Import of boot images started on %s" % rack.hostname,
            content_type=("text/plain; charset=%s" % settings.DEFAULT_CHARSET))

    @admin_method
    @operation(idempotent=True)
    def list_boot_images(self, request, system_id):
        """List all available boot images.

        Shows all available boot images and lists whether they are in sync with
        the region.

        Returns 404 if the rack controller is not found.
        """
        rack = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NODE_PERMISSION.VIEW)
        return rack.list_boot_images()

    @classmethod
    def resource_uri(cls, rackcontroller=None):
        rackcontroller_id = "system_id"
        if rackcontroller is not None:
            rackcontroller_id = rackcontroller.system_id
        return ('rackcontroller_handler', (rackcontroller_id, ))


class RackControllersHandler(NodesHandler, PowersMixin):
    """Manage the collection of all rack controllers in MAAS."""
    api_doc_section_name = "RackControllers"
    base_model = RackController

    @admin_method
    @operation(idempotent=False)
    def import_boot_images(self, request):
        """Import the boot images on all rack controllers."""
        # Avoid circular import.
        from maasserver.clusterrpc.boot_images import RackControllersImporter

        post_commit_do(RackControllersImporter.schedule)
        return HttpResponse(
            "Import of boot images started on all rack controllers",
            content_type=("text/plain; charset=%s" % settings.DEFAULT_CHARSET))

    @admin_method
    @operation(idempotent=True)
    def describe_power_types(self, request):
        """Query all of the rack controllers for power information.

        :return: a list of dicts that describe the power types in this format.
        """
        return get_all_power_types_from_racks()

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('rackcontrollers_handler', [])
