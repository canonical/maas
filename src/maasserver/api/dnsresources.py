# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `DNSResource`."""

from django.db.models.query import QuerySet
from formencode.validators import StringBool
from maasserver.api.support import (
    admin_method,
    OperationsHandler,
)
from maasserver.api.utils import get_optional_param
from maasserver.enum import NODE_PERMISSION
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms.dnsresource import DNSResourceForm
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


class DNSResourcesQuerySet(QuerySet):

    def __iter__(self):
        """Custom iterator which also includes implicit DNS records."""
        domain = None
        if self._domain_filter is not None:
            unvisited_domains = set()
            unvisited_domains.add(self._domain_filter)
        else:
            unvisited_domains = set(Domain.objects.all())
        for record in super().__iter__():
            # This works because the query always either contains a single
            # domain, or is sorted by domain.
            if record.domain != domain:
                domain = record.domain
                unvisited_domains.remove(domain)
                yield from self._generate_synthetic_rrdata(domain)
            yield record
        for domain in unvisited_domains:
            yield from self._generate_synthetic_rrdata(domain)

    def _generate_synthetic_rrdata(self, domain):
        rrdata = domain.render_json_for_related_rrdata(
            include_dnsdata=False, as_dict=True, user=self._user_filter)
        for name, value in rrdata.items():
            name = name.split('.')[0]
            # Remove redundant info (this is provided in the top
            # level 'fqdn' field).
            if (self._name_filter is not None and name != self._name_filter):
                continue
            items = []
            for rr in value:
                if (self._rrtype_filter is not None and
                        rr['rrtype'] != self._rrtype_filter):
                    continue
                del rr['name']
                items.append(rr)
            if len(items) > 0:
                resource = DNSResource(id=-1, name=name, domain=domain)
                resource._rrdata = items
                yield resource


def get_dnsresource_queryset(
        all_records: bool, domainname: str=None, name: str=None,
        rrtype: str=None, user=None):
    # If the domain is a name, make it an id.
    domain = None
    if domainname is not None:
        if domainname.isdigit():
            domain = Domain.objects.get_domain_or_404(
                domainname, user=user, perm=NODE_PERMISSION.VIEW)
        else:
            domain = Domain.objects.get_domain_or_404(
                "name:%s" % domainname, user=user,
                perm=NODE_PERMISSION.VIEW)
        query = domain.dnsresource_set.all().order_by('name')
    else:
        query = DNSResource.objects.all().order_by('domain_id', 'name')
    rrtype_filter = None
    name_filter = None
    if name is not None:
        query = query.filter(name=name)
        name_filter = name
    if rrtype is not None:
        query = query.filter(dnsdata__rrtype=rrtype)
        rrtype_filter = rrtype
    query = query.prefetch_related('ip_addresses', 'dnsdata_set')
    query = query.select_related('domain')
    # Note: This must be done last, otherwise our hacks to show additional
    # records won't work.
    if all_records is True:
        query.__class__ = DNSResourcesQuerySet
        query._name_filter = name_filter
        query._rrtype_filter = rrtype_filter
        query._domain_filter = domain
        # Note: the _user_filter should be set to None we want to display
        # all records, even for non-superusers.
        query._user_filter = user
    return query


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
        :param all: if True, also include implicit DNS records created for
            nodes registered in MAAS.
        """
        data = request.GET
        fqdn = data.get('fqdn', None)
        name = data.get('name', None)
        domainname = data.get('domain', None)
        rrtype = data.get('rrtype', None)
        if rrtype is not None:
            rrtype = rrtype.upper()
        _all = get_optional_param(
            request.GET, 'all', default=False, validator=StringBool)
        if domainname is None and name is None and fqdn is not None:
            # We need a type for resource separation.  If the user didn't give
            # us a rrtype, then assume it's an address of some sort.
            (name, domainname) = separate_fqdn(fqdn, rrtype)
        user = request.user
        return get_dnsresource_queryset(
            _all, domainname, name, rrtype, user)

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
        data = request.data.copy()
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
        form = DNSResourceForm(data=data, request=request)
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
        dnsresource_id = "id"
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
        rrdata = getattr(dnsresource, '_rrdata', None)
        if rrdata is not None:
            return None
        return dnsresource.ip_addresses.all()

    @classmethod
    def resource_records(cls, dnsresource):
        """Other data for this dnsresource."""
        # If the _rrdata field exists in the resource object, this is a
        # synthetic record created by the DNSResourcesQuerySet, because the
        # user has chosen to include implicit records.
        rrdata = getattr(dnsresource, '_rrdata', None)
        if rrdata is not None:
            return rrdata
        else:
            return dnsresource.dnsdata_set.all().order_by('rrtype')

    def read(self, request, id):
        """Read dnsresource.

        Returns 404 if the dnsresource is not found.
        """
        return DNSResource.objects.get_dnsresource_or_404(
            id, request.user, NODE_PERMISSION.VIEW)

    def update(self, request, id):
        """Update dnsresource.

        :param fqdn: Hostname (with domain) for the dnsresource.
        :param ip_address: Address to assign to the dnsresource.

        Returns 403 if the user does not have permission to update the
        dnsresource.
        Returns 404 if the dnsresource is not found.
        """
        dnsresource = DNSResource.objects.get_dnsresource_or_404(
            id, request.user, NODE_PERMISSION.ADMIN)
        form = DNSResourceForm(
            instance=dnsresource, data=request.data, request=request)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, id):
        """Delete dnsresource.

        Returns 403 if the user does not have permission to delete the
        dnsresource.
        Returns 404 if the dnsresource is not found.
        """
        dnsresource = DNSResource.objects.get_dnsresource_or_404(
            id, request.user, NODE_PERMISSION.ADMIN)
        dnsresource.delete()
        return rc.DELETED
