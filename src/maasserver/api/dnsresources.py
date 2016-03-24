# Copyright 2016 Canonical Ltd.  This software is licensed under the
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
from maasserver.models.dnsresource import separate_fqdn
from piston3.utils import rc


DISPLAYED_DNSRESOURCE_FIELDS = (
    'id',
    'fqdn',
    'address_ttl',
    'ip_addresses',
    'resource_records'
)


class DNSResourcesHandler(OperationsHandler):
    """Manage dnsresources."""
    api_doc_section_name = "DNSResources"
    update = delete = None

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ('dnsresources_handler', [])

    def read(self, request):
        """List all resources for the specified criteria.

        :param domain: restrict the listing to entries for the domain.
        :param name: restrict the listing to entries of the given name.
        :param rrtype: restrict the listing to entries which have
            records of the given rrtype.
        """
        data = request.GET
        fqdn = data.get('fqdn', None)
        name = data.get('name', None)
        domainname = data.get('domain', None)
        rrtype = data.get('rrtype', None)
        if domainname is None and name is None and fqdn is not None:
            # We need a type for resource separation.  If the user didn't give
            # us a rrtype, then assume it's an address of some sort.
            (name, domainname) = separate_fqdn(fqdn, rrtype)
        # If the domain is a name, make it an id.
        if domainname is not None:
            if domainname.isdigit():
                domain = Domain.objects.get_domain_or_404(
                    domainname, user=request.user, perm=NODE_PERMISSION.VIEW)
            else:
                domain = Domain.objects.get_domain_or_404(
                    "name:%s" % domainname, user=request.user,
                    perm=NODE_PERMISSION.VIEW)
            query = domain.dnsresource_set.all().order_by('name')
        else:
            query = DNSResource.objects.all().order_by('domain_id', 'name')
        if name is not None:
            query = query.filter(name=name)
        if rrtype is not None:
            query = query.filter(dnsdata__rrtype=rrtype)
        return query

    @admin_method
    def create(self, request):
        """Create a dnsresource.

        :param fqdn: Hostname (with domain) for the dnsresource.  Either fqdn
            or (name, domain) must be specified.  Fqdn is ignored if either
            name or domain is given.
        :param name: Hostname (without domain)
        :param domain: Domain (name or id)
        :param address_ttl: Default ttl for entries in this zone.
        :param ip_addresses: (optional) Address (ip or id) to assign to the
            dnsresource.
        """
        data = request.data
        fqdn = data.get('fqdn', None)
        name = data.get('name', None)
        domainname = data.get('domain', None)
        # If the user gave us fqdn and did not give us name/domain, expand
        # fqdn.
        if domainname is None and name is None and fqdn is not None:
            # Assume that we're working with an address, since we ignore
            # rrtype and rrdata.
            (name, domainname) = separate_fqdn(fqdn, 'A')
            data['domain'] = domainname
            data['name'] = name
        # If the domain is a name, make it an id.
        if domainname is not None:
            if domainname.isdigit():
                domain = Domain.objects.get_domain_or_404(
                    domainname, user=request.user, perm=NODE_PERMISSION.VIEW)
            else:
                domain = Domain.objects.get_domain_or_404(
                    "name:%s" % domainname, user=request.user,
                    perm=NODE_PERMISSION.VIEW)
            data['domain'] = domain.id
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

    @classmethod
    def resource_records(cls, dnsresource):
        """Other data for this dnsresource."""
        return dnsresource.dnsdata_set.all().order_by('rrtype')

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
