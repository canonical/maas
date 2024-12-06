# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from django.core.handlers.wsgi import WSGIRequest
from piston3.utils import rc

from maasserver.api.support import admin_method, OperationsHandler
from maasserver.dhcp import configure_dhcp_on_agents
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms.reservedip import ReservedIPForm
from maasserver.models import ReservedIP
from maasserver.utils.orm import post_commit_do

DISPLAYED_RESERVEDIP_FIELDS = (
    "id",
    "ip",
    "subnet",
    "mac_address",
    "comment",
)


class ReservedIpsHandler(OperationsHandler):
    """Manage Reserved IPs."""

    api_doc_section_name = "Reserved IPs"
    update = delete = None
    fields = DISPLAYED_RESERVEDIP_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return "reservedips_handler", []

    def read(self, request: WSGIRequest):
        """@description-title List all available Reserved IPs
        @description List all IPs that have been reserved in MAAS.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a list of
        reserved IPs.
        """
        return ReservedIP.objects.all()

    @admin_method
    def create(self, request: WSGIRequest):
        """@description-title Create a Reserved IP
        @description Create a new Reserved IP.

        @param (string) "ip" [required=true] The IP to be reserved.

        @param (int) "subnet" [required=false] ID of the subnet associated with
        the IP to be reserved.

        @param (string) "mac_address" [required=false] The MAC address that
        should be linked to the reserved IP.

        @param (string) "comment" [required=false] A description of this
        reserved IP.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing information
        about the reserved IP.

        @error (http-status-code) "400" 400
        @error (content) "bad-params" IP parameter is required, and cannot be
        null or reserved. MAC address and VLAN need to be a unique together. IP
        needs to be within the subnet range. Subnet and VLAN for the reserved
        IP needs to be defined in MAAS.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to
        create the reserved IP.
        """
        form = ReservedIPForm(data=request.data)
        if form.is_valid():
            reserved_ip = form.save()

            # Trigger the update on the agents after the transaction is committed.
            post_commit_do(
                configure_dhcp_on_agents, reserved_ip_ids=[reserved_ip.id]
            )
            return reserved_ip
        else:
            raise MAASAPIValidationError(form.errors)


class ReservedIpHandler(OperationsHandler):
    """Manage Reserved IP."""

    api_doc_section_name = "Reserved IP"
    create = None
    model = ReservedIP
    fields = DISPLAYED_RESERVEDIP_FIELDS

    @classmethod
    def resource_uri(cls, reserved_ip=None):
        # See the comment in NodeHandler.resource_uri.
        reserved_id = "id"
        if reserved_ip is not None:
            reserved_id = reserved_ip.id
        return "reservedip_handler", (reserved_id,)

    def read(self, request: WSGIRequest, id: int):
        """@description-title Read a Reserved IP
        @description Read a reserved IP given its ID.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a list of
        reserved IPs.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested reserved IP is not found.
        """
        reserved_ip = ReservedIP.objects.get_reserved_ip_or_404(id)
        return reserved_ip

    @admin_method
    def update(self, request: WSGIRequest, id: int):
        """@description-title Update a reserved IP
        @description Update a reserved IP given its ID.

        @param (int) "{id}" [required=true] The ID of the Reserved IP to be
        updated.

        @param (string) "comment" [required=false] A description of this
        reserved IP.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the requested
        reserved IP.

        @error (http-status-code) "400" 400
        @error (content) "bad-params" IP is updated to a value belonging to
        another subnet. IP is updated to an IP already reserved.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to
        update the reserved IP.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested reserved IP range is not found.
        """
        reserved_ip = ReservedIP.objects.get_reserved_ip_or_404(id)
        form = ReservedIPForm(instance=reserved_ip, data=request.data)
        if form.is_valid():
            # No need to trigger the dhcp workflow because it's not possible to update the mac or the ip of a reserved ip.
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    @admin_method
    def delete(self, request: WSGIRequest, id: int):
        """@description-title Delete a reserved IP
        @description Delete a reserved IP given its ID.

        @param (int) "{id}" [required=true] The ID of the Reserved IP to be
        deleted.

        @success (http-status-code) "server-success" 204

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to
        delete the reserved IP.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested reserved IP is not found.
        """
        reserved_ip = ReservedIP.objects.get_reserved_ip_or_404(id)
        reserved_ip.delete()

        # Trigger the update on the agents after the transaction is committed.
        post_commit_do(
            configure_dhcp_on_agents, subnet_ids=[reserved_ip.subnet.id]
        )

        return rc.DELETED
