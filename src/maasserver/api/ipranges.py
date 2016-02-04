# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `ip-ranges`."""

from maasserver.api.support import (
    admin_method,
    OperationsHandler,
)
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms_iprange import IPRangeForm
from maasserver.models import IPRange
from piston3.utils import rc


DISPLAYED_IPRANGE_FIELDS = (
    'id',
    'type',
    'start_ip',
    'end_ip',
    'comment',
    'user',
    'subnet',
)


class IPRangesHandler(OperationsHandler):
    """Manage IP ranges."""
    api_doc_section_name = "IP Ranges"
    update = delete = None
    fields = DISPLAYED_IPRANGE_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ('ipranges_handler', [])

    def read(self, request):
        """List all IP ranges."""
        return IPRange.objects.all()

    @admin_method
    def create(self, request):
        """Create an IP range.

        :param type: Type of this range. (`dynamic` or `reserved`)
        :param start_ip: Start IP address of this range (inclusive).
        :param end_ip: End IP address of this range (inclusive).
        :param subnet: Subnet this range is associated with. (optional)
        """
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
        iprange_id = "iprange_id"
        if iprange is not None:
            iprange_id = iprange.id
        return ('iprange_handler', (iprange_id,))

    def read(self, request, iprange_id):
        """Read IP range.

        Returns 404 if the IP range is not found.
        """
        iprange = IPRange.objects.get_iprange_or_404(iprange_id)
        return iprange

    def update(self, request, iprange_id):
        """Update IP range.

        :param start_ip: Start IP address of this range (inclusive).
        :param end_ip: End IP address of this range (inclusive).

        Returns 404 if the IP Range is not found.
        """
        iprange = IPRange.objects.get_iprange_or_404(iprange_id)
        form = IPRangeForm(instance=iprange, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, iprange_id):
        """Delete IP range.

        Returns 404 if the IP range is not found.
        """
        iprange = IPRange.objects.get_iprange_or_404(iprange_id)
        iprange.delete()
        return rc.DELETED
