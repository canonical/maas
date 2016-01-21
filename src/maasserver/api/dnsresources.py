# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `DNSResource`."""

from maasserver.api.support import (
    admin_method,
    OperationsHandler,
)
from maasserver.enum import NODE_PERMISSION
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms_dnsresource import DNSResourceForm
from maasserver.models import (
    DNSResource,
    Domain,
)
from piston3.utils import rc


DISPLAYED_DNSRESOURCE_FIELDS = (
    'id',
    'fqdn',
    'address_ttl',
    'ip_addresses'
)


class DNSResourcesHandler(OperationsHandler):
    """Manage dnsresources."""
    api_doc_section_name = "DNSResources"
    update = delete = None
    fields = DISPLAYED_DNSRESOURCE_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ('dnsresources_handler', [])

    def read(self, request):
        """List all dnsresources."""
        return DNSResource.objects.all().order_by('domain__id')

    @admin_method
    def create(self, request):
        """Create a dnsresource.

        :param fqdn: Hostname (with domain) for the dnsresource.  Either fqdn
            or (name, domain) must be specified.  Fqdn is ignored if either
            name or domain is given.
        :param name: Hostname (without domain)
        :param domain: Domain (name or id)
        :param address_ttl: Default ttl for entries in this zone.
        :param ip_addresses: Address (ip or id) to assign to the dnsresource.
        """
        data = request.data
        fqdn = data.get('fqdn', None)
        name = data.get('name', None)
        domain = data.get('domain', None)
        # If the domain is a name, make it an id.  If the user gave us fqdn and
        # did not give us name/domain, expand fqdn.
        if domain is not None:
            if not domain.isdigit():
                domain = Domain.objects.get_domain_or_404(
                    "name:%s" % domain, user=request.user,
                    perm=NODE_PERMISSION.VIEW)
                data['domain'] = domain.id
        elif name is None and fqdn is not None:
            if fqdn.find('.') > -1:
                (name, domain) = fqdn.split('.', 1)
                domain = Domain.objects.get_domain_or_404(
                    "name:%s" % domain, user=request.user,
                    perm=NODE_PERMISSION.VIEW)
                data['domain'] = domain.id
                data['name'] = name
        form = DNSResourceForm(data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)


class DNSResourceHandler(OperationsHandler):
    """Manage dnsresource."""
    api_doc_section_name = "DNSResource"
    create = None
    model = DNSResource
    fields = DISPLAYED_DNSRESOURCE_FIELDS

    @classmethod
    def resource_uri(cls, dnsresource=None):
        # See the comment in NodeHandler.resource_uri.
        dnsresource_id = "dnsresource_id"
        if dnsresource is not None:
            dnsresource_id = dnsresource.id
        return ('dnsresource_handler', (dnsresource_id,))

    @classmethod
    def name(cls, dnsresource):
        """Return the name of the dnsresource."""
        return dnsresource.get_name()

    @classmethod
    def ip_addresses(cls, dnsresource):
        """Return IPAddresses within the specified dnsresource."""
        return dnsresource.ip_addresses.all()

    def read(self, request, dnsresource_id):
        """Read dnsresource.

        Returns 404 if the dnsresource is not found.
        """
        return DNSResource.objects.get_dnsresource_or_404(
            dnsresource_id, request.user, NODE_PERMISSION.VIEW)

    def update(self, request, dnsresource_id):
        """Update dnsresource.

        :param fqdn: Hostname (with domain) for the dnsresource.
        :param ip_address: Address to assign to the dnsresource.

        Returns 403 if the user does not have permission to update the
        dnsresource.
        Returns 404 if the dnsresource is not found.
        """
        dnsresource = DNSResource.objects.get_dnsresource_or_404(
            dnsresource_id, request.user, NODE_PERMISSION.ADMIN)
        form = DNSResourceForm(instance=dnsresource, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, dnsresource_id):
        """Delete dnsresource.

        Returns 403 if the user does not have permission to delete the
        dnsresource.
        Returns 404 if the dnsresource is not found.
        """
        dnsresource = DNSResource.objects.get_dnsresource_or_404(
            dnsresource_id, request.user, NODE_PERMISSION.ADMIN)
        dnsresource.delete()
        return rc.DELETED
