# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `NodeDevice`."""

from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from piston3.utils import rc

from maasserver.api.support import admin_method, OperationsHandler
from maasserver.api.utils import get_optional_param
from maasserver.exceptions import MAASAPIValidationError
from maasserver.models import Node, NodeDevice
from maasserver.models.nodedevice import translate_bus
from maasserver.models.script import translate_hardware_type
from maasserver.permissions import NodePermission


class NodeDevicesHandler(OperationsHandler):
    """View NodeDevices from a Node."""

    api_doc_section_name = "Node Devices"

    create = update = delete = None

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ("node_devices_handler", ["system_id"])

    def read(self, request, system_id):
        """@description-title Return node devices
        @description Return a list of devices attached to the node given by
        a system_id.

        @param (string) "{system_id}" [required=true] The node's system_id.

        @param (string) "bus" [required=false] Only return devices attached to
        the specified bus. Can be PCIE or USB. Defaults to all.

        @param (string) "hardware_type" [required=false] Only return scripts
        for the given hardware type.  Can be ``node``, ``cpu``, ``memory``,
        ``storage`` or ``gpu``.  Defaults to all.

        @param (string) "vendor_id" [required=false] Only return devices which
        have the specified vendor id.

        @param (string) "product_id" [required=false] Only return devices which
        have the specified product id.

        @param (string) "vendor_name" [required=false] Only return devices
        which have the specified vendor_name.

        @param (string) "product_name" [required=false] Only return devices
        which have the specified product_name.

        @param (string) "commissioning_driver" [required=false] Only return
        devices which use the specified driver when commissioning.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a list of
        script result objects.
        @success-example "success-json" [exkey=script-results-read]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No Node matches the given query.
        """
        node = Node.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.view
        )
        qs = node.current_config.nodedevice_set.prefetch_related(
            "node_config__node",
            "numa_node",
            "physical_interface",
            "physical_blockdevice",
        )

        bus = get_optional_param(request.GET, "bus")
        if bus is not None:
            try:
                bus = translate_bus(bus)
            except ValidationError as e:
                raise MAASAPIValidationError(e)  # noqa: B904
            else:
                qs = qs.filter(bus=bus)

        hardware_type = get_optional_param(request.GET, "hardware_type")
        if hardware_type is not None:
            try:
                hardware_type = translate_hardware_type(hardware_type)
            except ValidationError as e:
                raise MAASAPIValidationError(e)  # noqa: B904
            else:
                qs = qs.filter(hardware_type=hardware_type)

        vendor_id = get_optional_param(request.GET, "vendor_id")
        if vendor_id is not None:
            qs = qs.filter(vendor_id__iexact=vendor_id)

        product_id = get_optional_param(request.GET, "product_id")
        if product_id is not None:
            qs = qs.filter(product_id__iexact=product_id)

        vendor_name = get_optional_param(request.GET, "vendor_name")
        if vendor_name is not None:
            qs = qs.filter(vendor_name__iexact=vendor_name)

        product_name = get_optional_param(request.GET, "product_name")
        if product_name is not None:
            qs = qs.filter(product_name__iexact=product_name)

        commissioning_driver = get_optional_param(
            request.GET, "commissioning_driver"
        )
        if commissioning_driver is not None:
            qs = qs.filter(commissioning_driver__iexact=commissioning_driver)

        return qs


class NodeDeviceHandler(OperationsHandler):
    """View a specific NodeDevice from a Node."""

    api_doc_section_name = "Node Device"

    fields = (
        "id",
        "bus",
        "bus_name",
        "hardware_type",
        "hardware_type_name",
        "system_id",
        "numa_node",
        "physical_blockdevice",
        "physical_interface",
        "vendor_id",
        "product_id",
        "vendor_name",
        "product_name",
        "commissioning_driver",
        "bus_number",
        "device_number",
        "pci_address",
    )
    model = NodeDevice

    create = update = None

    @classmethod
    def resource_uri(cls, node_device=None):
        # See the comment in NodeHandler.resource_uri.
        if node_device is None:
            system_id = "system_id"
            node_device_id = "id"
        else:
            system_id = node_device.node_config.node.system_id
            node_device_id = node_device.id
        return ("node_device_handler", [system_id, node_device_id])

    @classmethod
    def bus_name(cls, node_device):
        return node_device.get_bus_display()

    @classmethod
    def hardware_type_name(cls, node_device):
        return node_device.get_hardware_type_display()

    @classmethod
    def system_id(cls, node_device):
        return node_device.node_config.node.system_id

    @classmethod
    def numa_node(cls, node_device):
        return node_device.numa_node.index

    def _get_node_device(self, request, system_id, id):
        node = Node.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.view
        )
        node_config = node.current_config
        if id.isdigit():
            return get_object_or_404(
                NodeDevice, node_config=node_config, id=id
            )
        else:
            try:
                split_id = id.split(":")
                if len(split_id) == 2:
                    return get_object_or_404(
                        NodeDevice,
                        node_config=node_config,
                        bus_number=int(split_id[0]),
                        device_number=int(split_id[1]),
                    )
                else:
                    return get_object_or_404(
                        NodeDevice,
                        node_config=node_config,
                        pci_address=id,
                    )
            except Exception:
                raise MAASAPIValidationError("Invalid id format!")  # noqa: B904

    def read(self, request, system_id, id):
        """@description-title Return a specific node device
        @description Return a node device with the given system_id and node
        device id.

        @param (string) "{system_id}" [required=true] A system_id.

        @param (int) "{id}" [required=true] A node device id.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the new
        requested node device object.
        @success-example "success-json" [exkey=node-devices-read-by-id]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested node or node device is
        not found.
        @error-example "not-found"
            No Node matches the given query.
        """
        return self._get_node_device(request, system_id, id)

    @admin_method
    def delete(self, request, system_id, id):
        """@description-title Delete a node device
        @description Delete a node device with the given system_id and id.
        If the device is still present in the system it will be recreated
        when the node is commissioned.

        @param (string) "{system_id}" [required=true] A system_id

        @param (string) "{id}" [required=true] A node device id.

        @success (http-status-code) "server-success" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested node or node device is
        not found.
        @error-example "not-found"
            No Node matches the given query.
        """
        node_device = self._get_node_device(request, system_id, id)
        node_device.delete()
        return rc.DELETED
