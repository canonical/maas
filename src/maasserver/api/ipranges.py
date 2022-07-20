# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `ip-ranges`."""

from piston3.utils import rc

from maasserver.api.support import OperationsHandler
from maasserver.enum import IPRANGE_TYPE
from maasserver.exceptions import MAASAPIForbidden, MAASAPIValidationError
from maasserver.forms.iprange import IPRangeForm
from maasserver.models import IPRange

DISPLAYED_IPRANGE_FIELDS = (
    "id",
    "type",
    "start_ip",
    "end_ip",
    "comment",
    "user",
    "subnet",
)


def raise_error_if_not_owner(iprange, user):
    if not user.is_superuser and iprange.user_id != user.id:
        raise MAASAPIForbidden(
            "Unable to modify IP range. You don't own the IP range."
        )


class IPRangesHandler(OperationsHandler):
    """Manage IP ranges."""

    api_doc_section_name = "IP Ranges"
    update = delete = None
    fields = DISPLAYED_IPRANGE_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ("ipranges_handler", [])

    def read(self, request):
        """@description-title List all IP ranges
        @description List all available IP ranges.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a list of IP
        ranges.
        @success-example "success-json" [exkey=ipranges-read] placeholder text
        """
        return IPRange.objects.all()

    def create(self, request):
        """@description-title Create an IP range
        @description Create a new IP range.

        @param (string) "type" [required=true] Type of this range. (``dynamic``
        or ``reserved``)

        @param (string) "start_ip" [required=true] Start IP address of this
        range (inclusive).

        @param (string) "end_ip" [required=true] End IP address of this range
        (inclusive).

        @param (string) "subnet" [required=true] Subnet associated with this
        range.

        @param (string) "comment" [required=false] A description of this range.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the new IP
        range.
        @success-example "success-json" [exkey=ipranges-create] placeholder
        text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have the permissions
        required to create an IP range.
        """
        if (
            "type" in request.data
            and request.data["type"] == IPRANGE_TYPE.DYNAMIC
            and not request.user.is_superuser
        ):
            raise MAASAPIForbidden(
                "Unable to create dynamic IP range. "
                "You don't have sufficient privileges."
            )

        form = IPRangeForm(data=request.data, request=request)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)


class IPRangeHandler(OperationsHandler):
    """Manage IP range."""

    api_doc_section_name = "IP Range"
    create = None
    model = IPRange
    fields = DISPLAYED_IPRANGE_FIELDS

    @classmethod
    def resource_uri(cls, iprange=None):
        # See the comment in NodeHandler.resource_uri.
        iprange_id = "id"
        if iprange is not None:
            iprange_id = iprange.id
        return ("iprange_handler", (iprange_id,))

    def read(self, request, id):
        """@description-title Read an IP range
        @description Read an IP range with the given id.

        @param (int) "{id}" [required=true] An IP range id.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the requested
        IP range.
        @success-example "success-json" [exkey=ipranges-read-by-id] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested IP range is not found.
        @error-example "not-found"
            No IPRange matches the given query.
        """
        iprange = IPRange.objects.get_iprange_or_404(id)
        return iprange

    def update(self, request, id):
        """@description-title Update an IP range
        @description Update an IP range with the given id.

        @param (int) "{id}" [required=true] An IP range id.

        @param (string) "start_ip" [required=false] Start IP address of this
        range (inclusive).

        @param (string) "end_ip" [required=false] End IP address of this range
        (inclusive).

        @param (string) "comment" [required=false] A description of this range.
        (optional)

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the requested
        IP range.
        @success-example "success-json" [exkey=ipranges-update] placeholder
        text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have the permissions
        required to update the IP range.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested IP range is not found.
        @error-example "not-found"
            No IPRange matches the given query.
        """
        iprange = IPRange.objects.get_iprange_or_404(id)
        raise_error_if_not_owner(iprange, request.user)
        form = IPRangeForm(instance=iprange, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, id):
        """@description-title Delete an IP range
        @description Delete an IP range with the given id.

        @param (int) "{id}" [required=true] An IP range id.

        @success (http-status-code) "server-success" 204

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have the permissions
        required to delete the IP range.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested IP range is not found.
        @error-example "not-found"
            No IPRange matches the given query.
        """
        iprange = IPRange.objects.get_iprange_or_404(id)
        raise_error_if_not_owner(iprange, request.user)
        iprange.delete()
        return rc.DELETED
