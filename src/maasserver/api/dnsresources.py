# Copyright 2016-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `DNSResource`."""

from django.db.models.query import QuerySet
from formencode.validators import StringBool
from piston3.utils import rc

from maasserver.api.support import admin_method, OperationsHandler
from maasserver.api.utils import get_optional_param
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms.dnsresource import DNSResourceForm
from maasserver.models import DNSResource, Domain
from maasserver.models.dnsresource import separate_fqdn
from maasserver.permissions import NodePermission

DISPLAYED_DNSRESOURCE_FIELDS = (
    "id",
    "fqdn",
    "address_ttl",
    "ip_addresses",
    "resource_records",
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
            include_dnsdata=False, as_dict=True, user=self._user_filter
        )
        for name, value in rrdata.items():
            name = name.split(".")[0]
            # Remove redundant info (this is provided in the top
            # level 'fqdn' field).
            if self._name_filter is not None and name != self._name_filter:
                continue
            items = []
            for rr in value:
                if (
                    self._rrtype_filter is not None
                    and rr["rrtype"] != self._rrtype_filter
                ):
                    continue
                del rr["name"]
                items.append(rr)
            if len(items) > 0:
                resource = DNSResource(id=-1, name=name, domain=domain)
                resource._rrdata = items
                yield resource


def get_dnsresource_queryset(
    all_records: bool,
    domainname: str = None,
    name: str = None,
    rrtype: str = None,
    user=None,
):
    # If the domain is a name, make it an id.
    domain = None
    if domainname is not None:
        if domainname.isdigit():
            domain = Domain.objects.get_domain_or_404(
                domainname, user=user, perm=NodePermission.view
            )
        else:
            domain = Domain.objects.get_domain_or_404(
                "name:%s" % domainname, user=user, perm=NodePermission.view
            )
        query = domain.dnsresource_set.all().order_by("name")
    else:
        query = DNSResource.objects.all().order_by("domain_id", "name")
    rrtype_filter = None
    name_filter = None
    if name is not None:
        query = query.filter(name=name)
        name_filter = name
    if rrtype is not None:
        query = query.filter(dnsdata__rrtype=rrtype)
        rrtype_filter = rrtype
    query = query.prefetch_related("ip_addresses", "dnsdata_set")
    query = query.select_related("domain")
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
        return ("dnsresources_handler", [])

    def read(self, request):
        """@description-title List resources
        @description List all resources for the specified criteria.

        @param (string) "fqdn" [required=false] Restricts the listing to
        entries for the fqdn.

        @param (string) "domain" [required=false] Restricts the listing to
        entries for the domain.

        @param (string) "name" [required=false] Restricts the listing to
        entries of the given name.

        @param (string) "rrtype" [required=false] Restricts the listing to
        entries which have records of the given rrtype.

        @param (boolean) "all" [required=false] Include implicit DNS records
        created for nodes registered in MAAS if true.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a list of the
        requested DNS resource objects.
        @success-example "success-json" [exkey=dnsresources-read] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested DNS resources are not found.
        @error-example "not-found"
            No DNSResource matches the given query.
        """
        data = request.GET
        fqdn = data.get("fqdn", None)
        name = data.get("name", None)
        domainname = data.get("domain", None)
        rrtype = data.get("rrtype", None)
        if rrtype is not None:
            rrtype = rrtype.upper()
        _all = get_optional_param(
            request.GET, "all", default=False, validator=StringBool
        )
        if domainname is None and name is None and fqdn is not None:
            # We need a type for resource separation.  If the user didn't give
            # us a rrtype, then assume it's an address of some sort.
            (name, domainname) = separate_fqdn(fqdn, rrtype)
        user = request.user
        return get_dnsresource_queryset(_all, domainname, name, rrtype, user)

    @admin_method
    def create(self, request):
        """@description-title Create a DNS resource
        @description Create a DNS resource.

        @param (string) "fqdn" [required=false] Hostname (with domain) for the
        dnsresource.  Either ``fqdn`` or ``name`` and ``domain`` must be
        specified.  ``fqdn`` is ignored if either ``name`` or ``domain`` is
        given.

        @param (string) "name" [required=true] Hostname (without domain).

        @param (string) "domain" [required=true] Domain (name or id).

        @param (string) "address_ttl" [required=false] Default TTL for entries
        in this zone.

        @param (string) "ip_addresses" [required=false] Address (ip or id) to
        assign to the dnsresource. This creates an A or AAAA record,
        for each of the supplied ip_addresses, IPv4 or IPv6, respectively.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the new DNS
        resource object.
        @success-example "success-json" [exkey=dnsresources-create] placeholder
        text
        """
        data = request.data.copy()
        fqdn = data.get("fqdn", None)
        name = data.get("name", None)
        domainname = data.get("domain", None)
        # If the user gave us fqdn and did not give us name/domain, expand
        # fqdn.
        if domainname is None and name is None and fqdn is not None:
            # Assume that we're working with an address, since we ignore
            # rrtype and rrdata.
            (name, domainname) = separate_fqdn(fqdn, "A")
            data["domain"] = domainname
            data["name"] = name
        # If the domain is a name, make it an id.
        if domainname is not None:
            if domainname.isdigit():
                domain = Domain.objects.get_domain_or_404(
                    domainname, user=request.user, perm=NodePermission.view
                )
            else:
                domain = Domain.objects.get_domain_or_404(
                    "name:%s" % domainname,
                    user=request.user,
                    perm=NodePermission.view,
                )
            data["domain"] = domain.id
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
        return ("dnsresource_handler", (dnsresource_id,))

    @classmethod
    def name(cls, dnsresource):
        """Return the name of the dnsresource."""
        return dnsresource.get_name()

    @classmethod
    def ip_addresses(cls, dnsresource):
        """Return IPAddresses within the specified dnsresource."""
        rrdata = getattr(dnsresource, "_rrdata", None)
        if rrdata is not None:
            return None
        return dnsresource.ip_addresses.all()

    @classmethod
    def resource_records(cls, dnsresource):
        """Other data for this dnsresource."""
        # If the _rrdata field exists in the resource object, this is a
        # synthetic record created by the DNSResourcesQuerySet, because the
        # user has chosen to include implicit records.
        rrdata = getattr(dnsresource, "_rrdata", None)
        if rrdata is not None:
            return rrdata
        else:
            return dnsresource.dnsdata_set.all().order_by("rrtype")

    def read(self, request, id):
        """@description-title Read a DNS resource
        @description Read a DNS resource by id.

        @param (int) "{id}" [required=true] The DNS resource id.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the requested
        DNS resource object.
        @success-example "success-json" [exkey=dnsresources-read-by-id]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested DNS resource is not found.
        @error-example "not-found"
            No DNSResource matches the given query.
        """
        return DNSResource.objects.get_dnsresource_or_404(
            id, request.user, NodePermission.view
        )

    def update(self, request, id):
        """@description-title Update a DNS resource
        @description Update a DNS resource with the given id.

        @param (int) "{id}" [required=true] The DNS resource id.

        @param (string) "fqdn" [required=false] Hostname (with domain) for the
        dnsresource.  Either ``fqdn`` or ``name`` and ``domain`` must be
        specified.  ``fqdn`` is ignored if either ``name`` or ``domain`` is
        given.

        @param (string) "name" [required=false] Hostname (without domain).

        @param (string) "domain" [required=false] Domain (name or id).

        @param (string) "address_ttl" [required=false] Default TTL for entries
        in this zone.

        @param (string) "ip_addresses" [required=false] Address (ip or id) to
        assign to the dnsresource. This creates an A or AAAA record,
        for each of the supplied ip_addresses, IPv4 or IPv6, respectively.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the updated DNS
        resource object.
        @success-example "success-json" [exkey=dnsresources-update] placeholder
        text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to update
        the requested DNS resource.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested DNS resource is not found.
        @error-example "not-found"
            No DNSResource matches the given query.
        """
        data = request.data.copy()
        fqdn = data.get("fqdn", None)
        name = data.get("name", None)
        domainname = data.get("domain", None)
        # If the user gave us fqdn and did not give us name/domain, expand
        # fqdn.
        if domainname is None and name is None and fqdn is not None:
            # Assume that we're working with an address, since we ignore
            # rrtype and rrdata.
            (name, domainname) = separate_fqdn(fqdn, "A")
            data["domain"] = domainname
            data["name"] = name
        # If the domain is a name, make it an id.
        if domainname is not None:
            if domainname.isdigit():
                domain = Domain.objects.get_domain_or_404(
                    domainname, user=request.user, perm=NodePermission.view
                )
            else:
                domain = Domain.objects.get_domain_or_404(
                    "name:%s" % domainname,
                    user=request.user,
                    perm=NodePermission.view,
                )
            data["domain"] = domain.id
        dnsresource = DNSResource.objects.get_dnsresource_or_404(
            id, request.user, NodePermission.admin
        )
        form = DNSResourceForm(
            instance=dnsresource, data=data, request=request
        )
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, id):
        """@description-title Delete a DNS resource
        @description Delete a DNS resource with the given id.

        @param (int) "{id}" [required=true] The DNS resource id.

        @success (http-status-code) "server-success" 204

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to update
        the requested DNS resource.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested DNS resource is not found.
        @error-example "not-found"
            No DNSResource matches the given query.
        """
        dnsresource = DNSResource.objects.get_dnsresource_or_404(
            id, request.user, NodePermission.admin
        )
        dnsresource.delete()
        return rc.DELETED
