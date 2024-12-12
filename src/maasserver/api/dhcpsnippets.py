# Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `DHCPSnippet`."""


from email.utils import format_datetime

from piston3.utils import rc

from maasserver.api.reservedip import ReservedIpHandler, ReservedIpsHandler
from maasserver.api.support import (
    admin_method,
    deprecated,
    operation,
    OperationsHandler,
)
from maasserver.audit import create_audit_event
from maasserver.enum import ENDPOINT
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms.dhcpsnippet import DHCPSnippetForm
from maasserver.models import DHCPSnippet
from provisioningserver.events import EVENT_TYPES

DISPLAYED_DHCP_SNIPPET_FIELDS = (
    "id",
    "name",
    "value",
    "history",
    "description",
    "enabled",
    "node",
    "subnet",
    "global_snippet",
)


@deprecated(use=ReservedIpHandler)
class DHCPSnippetHandler(OperationsHandler):
    """
    Manage an individual DHCP snippet.

    The DHCP snippet is identified by its id.
    """

    api_doc_section_name = "DHCP Snippet"
    create = None
    model = DHCPSnippet
    fields = DISPLAYED_DHCP_SNIPPET_FIELDS

    @classmethod
    def resource_uri(cls, dhcp_snippet=None):
        # See the comment in NodeHandler.resource_uri.
        if dhcp_snippet is not None:
            dhcp_snippet_id = dhcp_snippet.id
        else:
            dhcp_snippet_id = "id"
        return ("dhcp_snippet_handler", (dhcp_snippet_id,))

    @classmethod
    def value(handler, dhcp_snippet):
        return dhcp_snippet.value.data

    @classmethod
    def history(handler, dhcp_snippet):
        return [
            {
                "id": value.id,
                "value": value.data,
                "created": format_datetime(value.created),
            }
            for value in dhcp_snippet.value.previous_versions()
        ]

    @classmethod
    def global_snippet(handler, dhcp_snippet):
        return dhcp_snippet.node is None and dhcp_snippet.subnet is None

    def read(self, request, id):
        """@description-title Read a DHCP snippet
        @description Read a DHCP snippet with the given id.

        @param (int) "{id}" [required=true] A DHCP snippet id.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing
        information about the requested DHCP snippet.
        @success-example "success-json" [exkey=dhcp-snippets-read-by-id]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested DHCP snippet is not found.
        @error-example "not-found"
            No DHCPSnippet matches the given query.
        """
        return DHCPSnippet.objects.get_dhcp_snippet_or_404(id)

    @admin_method
    def update(self, request, id):
        """@description-title Update a DHCP snippet
        @description Update a DHCP snippet with the given id.

        @param (int) "{id}" [required=true] A DHCP snippet id.

        @param (string) "name" [required=false] The name of the DHCP snippet.

        @param (string) "value" [required=false] The new value of the DHCP
        snippet to be used in dhcpd.conf. Previous values are stored and can be
        reverted.

        @param (string) "description" [required=false] A description of what
        the DHCP snippet does.

        @param (boolean) "enabled" [required=false] Whether or not the DHCP
        snippet is currently enabled.

        @param (string) "node" [required=false] The node the DHCP snippet is to
        be used for. Can not be set if subnet is set.

        @param (string) "subnet" [required=false] The subnet the DHCP snippet
        is to be used for. Can not be set if node is set.

        @param (boolean) "global_snippet" [required=false] Set the DHCP snippet
        to be a global option. This removes any node or subnet links.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing
        information about the updated DHCP snippet.
        @success-example "success-json" [exkey=dhcp-snippets-update]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested DHCP snippet is not found.
        @error-example "not-found"
            No DHCPSnippet matches the given query.
        """
        dhcp_snippet = DHCPSnippet.objects.get_dhcp_snippet_or_404(id)
        form = DHCPSnippetForm(instance=dhcp_snippet, data=request.data)
        if form.is_valid():
            return form.save(ENDPOINT.API, request)
        else:
            raise MAASAPIValidationError(form.errors)

    @admin_method
    def delete(self, request, id):
        """@description-title Delete a DHCP snippet
        @description Delete a DHCP snippet with the given id.

        @param (int) "{id}" [required=true] A DHCP snippet id.

        @success (http-status-code) "server-success" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested DHCP snippet is not found.
        @error-example "not-found"
            No DHCPSnippet matches the given query.
        """
        dhcp_snippet = DHCPSnippet.objects.get_dhcp_snippet_or_404(id)
        dhcp_snippet.delete()
        create_audit_event(
            EVENT_TYPES.SETTINGS,
            ENDPOINT.API,
            request,
            None,
            description=("Deleted DHCP snippet '%s'." % dhcp_snippet.name),
        )
        return rc.DELETED

    @admin_method
    @operation(idempotent=False)
    def revert(self, request, id):
        """@description-title Revert DHCP snippet to earlier version
        @description Revert the value of a DHCP snippet with the given id to an
        earlier revision.

        @param (int) "{id}" [required=true] A DHCP snippet id.

        @param (int) "to" [required=true] What revision in the DHCP snippet's
        history to revert to.  This can either be an ID or a negative number
        representing how far back to go.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing
        information about the reverted DHCP snippet.
        @success-example "success-json" [exkey=dhcp-snippets-revert]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested DHCP snippet is not found.
        @error-example "not-found"
            No DHCPSnippet matches the given query.
        """
        revert_to = request.data.get("to")
        if revert_to is None:
            raise MAASAPIValidationError("You must specify where to revert to")
        try:
            revert_to = int(revert_to)
        except ValueError:
            raise MAASAPIValidationError(
                "%s is an invalid 'to' value" % revert_to
            )

        dhcp_snippet = DHCPSnippet.objects.get_dhcp_snippet_or_404(id)
        try:

            def gc_hook(value):
                dhcp_snippet.value = value
                dhcp_snippet.save()

            dhcp_snippet.value.revert(revert_to, gc_hook=gc_hook)
            create_audit_event(
                EVENT_TYPES.SETTINGS,
                ENDPOINT.API,
                request,
                None,
                description=(
                    "Reverted DHCP snippet '%s' to revision '%s'."
                    % (dhcp_snippet.name, revert_to)
                ),
            )
            return dhcp_snippet
        except ValueError as e:
            raise MAASAPIValidationError(e.args[0])


@deprecated(use=ReservedIpsHandler)
class DHCPSnippetsHandler(OperationsHandler):
    """Manage the collection of all DHCP snippets in MAAS."""

    api_doc_section_name = "DHCP Snippets"
    update = delete = None

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("dhcp_snippets_handler", [])

    def read(self, request):
        """@description-title List DHCP snippets
        @description List all available DHCP snippets.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a list of all
        available DHCP snippets.
        @success-example "success-json" [exkey=dhcp-snippets-read] placeholder
        text
        """
        return DHCPSnippet.objects.all().select_related(
            "value", "subnet", "node"
        )

    @admin_method
    def create(self, request):
        """@description-title Create a DHCP snippet
        @description Creates a DHCP snippet.

        @param (string) "name" [required=true] The name of the DHCP snippet.

        @param (string) "value" [required=true] The snippet of config inserted
        into dhcpd.conf.

        @param (string) "description" [required=false] A description of what
        the snippet does.

        @param (boolean) "enabled" [required=false] Whether or not the snippet
        is currently enabled.

        @param (string) "node" [required=false] The node this snippet applies
        to. Cannot be used with subnet or global_snippet.

        @param (string) "subnet" [required=false] The subnet this snippet
        applies to. Cannot be used with node or global_snippet.

        @param (string) "iprange" [required=false] The iprange within a subnet
        this snippet applies to. Must also provide a subnet value.

        @param (boolean) "global_snippet" [required=false] Whether or not this
        snippet is to be applied globally. Cannot be used with node or subnet.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the new DHCP
        snippet object.
        @success-example "success-json" [exkey=dhcp-snippets-create]
        placeholder text
        """
        form = DHCPSnippetForm(data=request.data)
        if form.is_valid():
            return form.save(ENDPOINT.API, request)
        else:
            raise MAASAPIValidationError(form.errors)
