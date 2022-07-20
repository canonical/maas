# Copyright 2016-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from formencode.validators import StringBool
from piston3.utils import rc

from maasserver.api.nodes import NodeHandler, NodesHandler
from maasserver.api.support import admin_method
from maasserver.api.utils import get_optional_param
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms import ControllerForm
from maasserver.models import RegionController
from maasserver.permissions import NodePermission

# Region controller's fields exposed on the API.
DISPLAYED_REGION_CONTROLLER_FIELDS = (
    "system_id",
    "hostname",
    "description",
    "hardware_uuid",
    "domain",
    "fqdn",
    "architecture",
    "cpu_count",
    "cpu_speed",
    "memory",
    "swap_size",
    "osystem",
    "distro_series",
    "power_type",
    "power_state",
    "ip_addresses",
    "interface_set",
    "zone",
    "status_action",
    "node_type",
    "node_type_name",
    "current_commissioning_result_id",
    "current_testing_result_id",
    "current_installation_result_id",
    "version",
    "commissioning_status",
    "commissioning_status_name",
    "testing_status",
    "testing_status_name",
    "cpu_test_status",
    "cpu_test_status_name",
    "memory_test_status",
    "memory_test_status_name",
    "network_test_status",
    "network_test_status_name",
    "storage_test_status",
    "storage_test_status_name",
    "other_test_status",
    "other_test_status_name",
    "hardware_info",
    "tag_names",
    "interface_test_status",
    "interface_test_status_name",
)


class RegionControllerHandler(NodeHandler):
    """
    Manage an individual region controller.

    The region controller is identified by its system_id.
    """

    api_doc_section_name = "RegionController"
    model = RegionController
    fields = DISPLAYED_REGION_CONTROLLER_FIELDS

    def delete(self, request, system_id):
        """@description-title Delete a region controller
        @description Deletes a region controller with the given system_id.

        A region controller cannot be deleted if it hosts pod virtual machines.
        Use `force` to override this behavior. Forcing deletion will also
        remove hosted pods.

        @param (string) "{system_id}" [required=true] The region controller's
        system_id.

        @param (boolean) "force" [required=false] Tells MAAS to override
        disallowing deletion of region controllers that host pod virtual
        machines.

        @success (http-status-code) "204" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested rack controller system_id
        is not found.
        @error-example "not-found"
            No RegionController matches the given query.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to
        delete the rack controller.

        @error (http-status-code) "400" 400
        @error (content) "cannot-delete" If MAAS is unable to delete the
        region controller.
        """
        node = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.admin
        )
        node.as_self().delete(
            force=get_optional_param(request.GET, "force", False, StringBool)
        )
        return rc.DELETED

    @admin_method
    def update(self, request, system_id):
        """@description-title Update a region controller
        @description Updates a region controller with the given system_id.

        @param (string) "{system_id}" [required=true] The region controller's
        system_id.

        @param (string) "description" [required=false] The new description for
        this given region controller.

        @param (string) "power_type" [required=false] The new power type for
        this region controller. If you use the default value, power_parameters
        will be set to the empty string.  Available to admin users.  See the
        `Power types`_ section for a list of the available power types.

        @param (string) "power_parameters_{param1}" [required=true] The new
        value for the 'param1' power parameter. Note that this is dynamic as
        the available parameters depend on the selected value of the region
        controller's power_type.  Available to admin users. See the `Power
        types`_ section for a list of the available power parameters for each
        power type.

        @param (boolean) "power_parameters_skip_check" [required=false] Whether
        or not the new power parameters for this region controller should be
        checked against the expected power parameters for the region
        controller's power type ('true' or 'false').  The default is 'false'.

        @param (string) "zone" [required=false] Name of a valid physical zone
        in which to place this region controller.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing the updated
        region controller object.
        @success-example (json) "success-json" [exkey=update] placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested region controller system_id
        is not found.
        @error-example "not-found"
            No RegionController matches the given query.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to
        update the region controller.
        @error-example "no-perms"
            This method is reserved for admin users.
        """
        region = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.admin
        )
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
        return ("regioncontroller_handler", (regioncontroller_id,))


class RegionControllersHandler(NodesHandler):
    """Manage the collection of all region controllers in MAAS."""

    api_doc_section_name = "RegionControllers"
    base_model = RegionController

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("regioncontrollers_handler", [])
