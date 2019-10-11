# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Fan Network`."""

from maasserver.api.support import admin_method, OperationsHandler
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms.fannetwork import FanNetworkForm
from maasserver.models import FanNetwork
from maasserver.permissions import NodePermission
from piston3.utils import rc


DISPLAYED_FANNETWORK_FIELDS = (
    "id",
    "name",
    "underlay",
    "overlay",
    "dhcp",
    "host_reserve",
    "bridge",
    "off",
)


class FanNetworksHandler(OperationsHandler):
    """Manage Fan Networks."""

    api_doc_section_name = "Fan Networks"
    update = delete = None
    fields = DISPLAYED_FANNETWORK_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ("fannetworks_handler", [])

    def read(self, request):
        """@description-title List fan networks
        @description List all fan networks.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a list of all
        fan networks.
        @success-example "success-json" [exkey=fannetworks-read] placeholder
        text
        """
        return FanNetwork.objects.all()

    @admin_method
    def create(self, request):
        """@description Create a fan network
        @description-title Create a fan network.

        @param (string) "name" [required=true] Name of the fan network.

        @param (string) "overlay" [required=true] The overlay network.

        @param (string) "underlay" [required=true] The underlay network.

        @param (boolean) "dhcp" [required=false] Configure DHCP server for
        overlay network.

        @param (int) "host_reserve" [required=false] The number of IP addresses
        to reserve for host.

        @param (string) "bridge" [required=false] Override bridge name.

        @param (boolean) "off" [required=false] Put this fan network in the
        configuration, but disable it.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the new fan
        network.
        @success-example "success-json" [exkey=fannetworks-read] placeholder
        text
        """
        form = FanNetworkForm(data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)


class FanNetworkHandler(OperationsHandler):
    """Manage Fan Network."""

    api_doc_section_name = "Fan Network"
    create = None
    model = FanNetwork
    fields = DISPLAYED_FANNETWORK_FIELDS

    @classmethod
    def resource_uri(cls, fannetwork=None):
        # See the comment in NodeHandler.resource_uri.
        fannetwork_id = "id"
        if fannetwork is not None:
            fannetwork_id = fannetwork.id
        return ("fannetwork_handler", (fannetwork_id,))

    def read(self, request, id):
        """@description-title Read a fan network
        @description Read a fan network with the given id.

        @param (int) "{id}" [required=true] The fan network id.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the requested
        fan network.
        @success-example "success-json" [exkey=fannetworks-read-by-id]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested fan network is not found.
        @error-example "not-found"
            Not Found
        """
        return FanNetwork.objects.get_fannetwork_or_404(
            id, request.user, NodePermission.view
        )

    def update(self, request, id):
        """@description-title Update a fan network
        @description Update a fan network with the given id.

        @param (int) "{id}" [required=true] The fan network id.

        @param (string) "name" [required=false] Name of the fan network.

        @param (string) "overlay" [required=false] The overlay network.

        @param (string) "underlay" [required=false] The underlay network.

        @param (boolean) "dhcp" [required=false] Configure DHCP server for
        overlay network.

        @param (int) "host_reserve" [required=false] The number of IP addresses
        to reserve for host.

        @param (string) "bridge" [required=false] Override bridge name.

        @param (boolean) "off" [required=false] Put this fan network in the
        configuration, but disable it.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the updated
        fan network.
        @success-example "success-json" [exkey=fannetworks-update] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested fan network is not found.
        @error-example "not-found"
            Not Found
        """
        fannetwork = FanNetwork.objects.get_fannetwork_or_404(
            id, request.user, NodePermission.admin
        )
        form = FanNetworkForm(instance=fannetwork, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, id):
        """@description-title Delete a fan network
        @description Deletes a fan network with the given id.

        @param (int) "{id}" [required=true] The fan network id.

        @success (http-status-code) "server-success" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested fan network is not found.
        @error-example "not-found"
            Not Found
        """
        fannetwork = FanNetwork.objects.get_fannetwork_or_404(
            id, request.user, NodePermission.admin
        )
        fannetwork.delete()
        return rc.DELETED
