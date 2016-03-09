# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

__all__ = [
    'RackControllerHandler',
    'RackControllersHandler',
    ]

from django.conf import settings
from django.http import HttpResponse
from maasserver.api.nodes import (
    NodeHandler,
    NodesHandler,
)
from maasserver.api.support import (
    admin_method,
    operation,
)
from maasserver.clusterrpc.power_parameters import (
    get_all_power_types_from_clusters,
)
from maasserver.enum import NODE_PERMISSION
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
    'memory',
    'swap_size',
    'osystem',
    'distro_series',
    'ip_addresses',
    ('interface_set', (
        'id',
        'name',
        'type',
        'vlan',
        'mac_address',
        'parents',
        'children',
        'tags',
        'enabled',
        'links',
        'params',
        'discovered',
        'effective_mtu',
        )),
    'zone',
    'status_action',
    'node_type',
    'node_type_name',
)


class RackControllerHandler(NodeHandler):
    """Manage an individual rack controller.

    The rack controller is identified by its system_id.
    """
    api_doc_section_name = "RackController"
    model = RackController
    fields = DISPLAYED_RACK_CONTROLLER_FIELDS

    @admin_method
    @operation(idempotent=False)
    def refresh(self, request, system_id):
        """Refresh the hardware information for a specific rack controller.

        Returns 404 if the rack-controller is not found.
        Returns 403 if the user does not have permission to refresh the rack.
        """
        rack = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NODE_PERMISSION.EDIT)
        rack.refresh()
        return HttpResponse(
            "Refresh of %s has begun" % rack.hostname,
            content_type=("text/plain; charset=%s" % settings.DEFAULT_CHARSET))

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

    @operation(idempotent=True)
    def describe_power_types(self, request):
        """Query all of the rack controllers for power information.

        :return: a list of dicts that describe the power types in this format.
        """
        return get_all_power_types_from_clusters()

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('rackcontrollers_handler', [])
