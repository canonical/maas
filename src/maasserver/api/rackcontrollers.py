# Copyright 2016-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from formencode.validators import StringBool
from piston3.utils import rc

from maasserver.api.nodes import (
    NodeHandler,
    NodesHandler,
    PowerMixin,
    PowersMixin,
)
from maasserver.api.support import admin_method, operation
from maasserver.api.utils import get_optional_param
from maasserver.clusterrpc.driver_parameters import get_all_power_types
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms import ControllerForm
from maasserver.models import BootResource, RackController
from maasserver.permissions import NodePermission

# Rack controller's fields exposed on the API.
DISPLAYED_RACK_CONTROLLER_FIELDS = (
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
    ("service_set", ("name", "status", "status_info")),
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


class RackControllerHandler(NodeHandler, PowerMixin):
    """
    Manage an individual rack controller.

    The rack controller is identified by its system_id.
    """

    api_doc_section_name = "RackController"
    model = RackController
    fields = DISPLAYED_RACK_CONTROLLER_FIELDS

    def delete(self, request, system_id):
        """@description-title Delete a rack controller
        @description Deletes a rack controller with the given system_id. A
        rack controller cannot be deleted if it is set to `primary_rack` on
        a `VLAN` and another rack controller cannot be used to provide DHCP
        for said VLAN. Use `force` to override this behavior.

        Using `force` will also allow deleting a rack controller that is
        hosting pod virtual machines. The pod will also be deleted.

        Rack controllers that are also region controllers will be converted
        to a region controller (and hosted pods will not be affected).

        @param (boolean) "force" [required=false] Always delete the rack
        controller even if it is the `primary_rack` on a `VLAN` and another
        rack controller cannot provide DHCP on that VLAN. This will disable
        DHCP on those VLANs.

        @success (http-status-code) "204" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested rack controller system_id
        is not found.
        @error-example "not-found"
            No RackController matches the given query.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permssions to
        delete the rack controller.

        @error (http-status-code) "400" 400
        @error (content) "cannot-delete" Unable to delete 'maas-run'; it is
        currently set as a primary rack controller on VLANs fabric-0.untagged
        and no other rack controller can provide DHCP.
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
        """@description-title Update a rack controller
        @description Updates a rack controller with the given system_id.

        @param (string) "description" [required=false] The new description for
        this given rack controller.

        @param (string) "power_type" [required=false] The new power type for
        the given rack controller. If you use the default value,
        power_parameters will be set to an empty string. See the
        `Power types`_ section for a list of available power types. Note that
        only admin users can set this parameter.

        @param (string) "power_parameters_{param}" [required=true] The new
        value for the 'param' power parameter. This is a dynamic parameter
        that depends on the rack controller's power_type. See the
        `Power types`_ section for a list of available parameters based on
        power type. Note that only admin users can set these parameters.

        @param (boolean) "power_parameters_skip_check" [required=false] If
        true, the new power parameters for the given rack controller will be
        checked against the expected parameters for the rack controller's power
        type. Default is false.

        @param (string) "zone" [required=false] The name of a valid zone in
        which to place the given rack controller.

        @param (string) "domain" [required=false] The domain for this
        controller. If not given the default domain is used.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing the updated
        rack-controller object.
        @success-example "success-json" [exkey=update] placeholder

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested rack controller system_id
        is not found.
        @error-example "not-found"
            No RackController matches the given query.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" This method is reserved for admin users.
        """
        rack = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.admin
        )
        form = ControllerForm(data=request.data, instance=rack)

        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    @admin_method
    @operation(idempotent=False)
    def import_boot_images(self, request, system_id):
        """@description-title Import boot images
        @description Import boot images on a given rack controller or all
        rack controllers. (deprecated)

        @param (string) "{system_id}" [required=true] A rack controller
        system_id.

        @success (http-status-code) "202" 202
        @success (content) "success-single" No action

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested rack controller system_id
        is not found.
        @error-example "not-found"
            No RackController matches the given query.
        """
        self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.admin
        )
        return rc.ACCEPTED

    @admin_method
    @operation(idempotent=True)
    def list_boot_images(self, request, system_id):
        """@description-title List available boot images
        @description Lists all available boot images for a given rack
        controller system_id and whether they are in sync with the
        region controller. (deprecated)

        @param (string) "{system_id}" [required=true] The rack controller
        system_id for which you want to list boot images.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested rack controller system_id
        is not found.
        @error-example "not-found"
            No RackController matches the given query.
        """
        self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.view
        )
        images = []
        for res in BootResource.objects.all():
            arch, subarch = res.split_arch()
            subarches = [subarch]
            if "subarches" in res.extra:
                subarches.extend(res.extra["subarches"].split(","))
            res_name = (
                res.name
                if res.bootloader_type is None
                else f"bootloader/{res.bootloader_type}"
            )
            images.append(
                {
                    "name": res_name,
                    "architecture": arch,
                    "subarches": sorted(set(subarches)),
                }
            )
        return {
            "images": images,
            "connected": True,
            "status": "synced",
        }

    @classmethod
    def resource_uri(cls, rackcontroller=None):
        rackcontroller_id = "system_id"
        if rackcontroller is not None:
            rackcontroller_id = rackcontroller.system_id
        return ("rackcontroller_handler", (rackcontroller_id,))


class RackControllersHandler(NodesHandler, PowersMixin):
    """Manage the collection of all rack controllers in MAAS."""

    api_doc_section_name = "RackControllers"
    base_model = RackController

    @admin_method
    @operation(idempotent=False)
    def import_boot_images(self, request):
        """@description-title Import boot images on all rack controllers
        @description Imports boot images on all rack controllers. (deprecated)

        @success (http-status-code) "202" 202
        @success (content) "success-all" No action
        """
        return rc.ACCEPTED

    @admin_method
    @operation(idempotent=True)
    def describe_power_types(self, request):
        """@description-title Get power information from rack controllers
        @description Queries all rack controllers for power information.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing a dictionary
        with system_ids as keys and power parameters as values.
        @success-example "success-json" [exkey=power-params-multi] placeholder
        """
        return get_all_power_types()

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("rackcontrollers_handler", [])
