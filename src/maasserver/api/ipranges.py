# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `ip-ranges`."""

from maasserver.api.support import OperationsHandler
from maasserver.enum import IPRANGE_TYPE
from maasserver.exceptions import (
    MAASAPIForbidden,
    MAASAPIValidationError,
)
from maasserver.forms.iprange import IPRangeForm
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


def raise_error_if_not_owner(iprange, user):
    if not user.is_superuser and iprange.user_id != user.id:
        raise MAASAPIForbidden(
            "Unable to modify IP range. You don't own the IP range.")


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

    def create(self, request):
        """Create an IP range.

        :param type: Type of this range. (`dynamic` or `reserved`)
        :param start_ip: Start IP address of this range (inclusive).
        :param end_ip: End IP address of this range (inclusive).
        :param subnet: Subnet this range is associated with. (optional)
        :param comment: A description of this range. (optional)

        Returns 403 if standard users tries to create a dynamic IP range.
        """
        if ('type' in request.data and
                request.data['type'] == IPRANGE_TYPE.DYNAMIC and
                not request.user.is_superuser):
            raise MAASAPIForbidden(
                "Unable to create dynamic IP range. "
                "You don't have sufficient privileges.")

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
        return ('iprange_handler', (iprange_id,))

    def read(self, request, id):
        """Read IP range.

        Returns 404 if the IP range is not found.
        """
        iprange = IPRange.objects.get_iprange_or_404(id)
        return iprange

    def update(self, request, id):
        """Update IP range.

        :param start_ip: Start IP address of this range (inclusive).
        :param end_ip: End IP address of this range (inclusive).
        :param comment: A description of this range. (optional)

        Returns 403 if not owner of IP range.
        Returns 404 if the IP Range is not found.
        """
        iprange = IPRange.objects.get_iprange_or_404(id)
        raise_error_if_not_owner(iprange, request.user)
        form = IPRangeForm(instance=iprange, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, id):
        """Delete IP range.

        Returns 403 if not owner of IP range.
        Returns 404 if the IP range is not found.
        """
        iprange = IPRange.objects.get_iprange_or_404(id)
        raise_error_if_not_owner(iprange, request.user)
        iprange.delete()
        return rc.DELETED
