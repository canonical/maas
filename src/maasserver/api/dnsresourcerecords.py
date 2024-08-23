# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `DNSData`."""

from piston3.utils import rc

from maasserver.api.support import admin_method, OperationsHandler
from maasserver.exceptions import MAASAPIBadRequest, MAASAPIValidationError
from maasserver.forms.dnsdata import DNSDataForm
from maasserver.forms.dnsresource import DNSResourceForm
from maasserver.models import DNSData, DNSResource, Domain
from maasserver.models.dnsresource import separate_fqdn
from maasserver.permissions import NodePermission

DISPLAYED_DNSDATA_FIELDS = ("id", "fqdn", "ttl", "rrtype", "rrdata")


class DNSResourceRecordsHandler(OperationsHandler):
    """Manage DNS resource records (e.g. CNAME, MX, NS, SRV, TXT)"""

    api_doc_section_name = "DNSResourceRecords"
    update = delete = None

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ("dnsresourcerecords_handler", [])

    def read(self, request):
        """@description-title List all DNS resource records
        @description List all DNS resource records.

        @param (string) "fqdn" [required=false] Restricts the listing to
        entries for the fqdn.

        @param (string) "domain" [required=false] Restricts the listing to
        entries for the domain.

        @param (string) "name" [required=false] Restricts the listing to
        entries of the given name.

        @param (string) "rrtype" [required=false] Restricts the listing to
        entries which have records of the given rrtype.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a list of the
        requested DNS resource record objects.
        @success-example "success-json" [exkey=dnsresourcerecords-read]
        placeholder text
        """
        data = request.GET
        fqdn = data.get("fqdn", None)
        name = data.get("name", None)
        domainname = data.get("domain", None)
        rrtype = data.get("rrtype", None)
        if domainname is None and name is None and fqdn is not None:
            # We need a type for resource separation.  If the user didn't give
            # us a rrtype, then assume it's an address of some sort.
            (name, domainname) = separate_fqdn(fqdn, rrtype)
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
            query = DNSData.objects.filter(
                dnsresource__domain_id=domain.id
            ).order_by("dnsresource__name")
        else:
            query = DNSData.objects.all().order_by(
                "dnsresource__domain_id", "dnsresource__name"
            )
        if name is not None:
            query = query.filter(dnsresource__name=name)
        if rrtype is not None:
            query = query.filter(rrtype=rrtype)
        return query

    @admin_method
    def create(self, request):
        """@description-title Create a DNS resource record
        @description Create a new DNS resource record.

        @param (string) "fqdn" [required=false] Hostname (with domain) for the
        dnsresource.  Either ``fqdn`` or ``name`` and  ``domain`` must be
        specified.  ``fqdn`` is ignored if either name or domain is given (e.g.
        www.your-maas.maas).

        @param (string) "name" [required=false] The name (or hostname without a
        domain) of the DNS resource record (e.g. www.your-maas)

        @param (string) "domain" [required=false] The domain (name or id) where
        to create the DNS resource record (Domain (e.g. 'maas')

        @param (string) "rrtype" [required=false] The resource record type (e.g
        ``cname``, ``mx``, ``ns``, ``srv``, ``sshfp``, ``txt``).

        @param (string) "rrdata" [required=false] The resource record data
        (e.g. 'your-maas', '10 mail.your-maas.maas')

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the new DNS
        resource record object.
        @success-example "success-json" [exkey=dnsresourcerecords-create]
        placeholder text
        """
        data = request.data.copy()
        domain = None
        fqdn = data.get("fqdn", None)
        name = data.get("name", None)
        domainname = data.get("domain", None)
        rrtype = data.get("rrtype", None)
        rrdata = data.get("rrdata", None)
        if rrtype is None:
            raise MAASAPIBadRequest("rrtype must be provided.")
        if rrdata is None:
            raise MAASAPIBadRequest("rrdata must be provided.")
        # If the user gave us fqdn and did not give us name/domain, expand
        # fqdn.
        if domainname is None and name is None and fqdn is not None:
            (name, domainname) = separate_fqdn(fqdn, rrtype)
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
        if domain is None or name is None:
            raise MAASAPIValidationError(
                "Either name and domain (or fqdn) must be specified"
            )
        # Do we already have a DNSResource for this fqdn?
        dnsrr = (
            DNSResource.objects.filter(name=name, domain__id=domain.id)
            .values("id")
            .first()
        )
        if dnsrr is None:
            form = DNSResourceForm(data=data, request=request)
            if form.is_valid():
                dnsrr_id = form.save().id
            else:
                raise MAASAPIValidationError(form.errors)
        else:
            dnsrr_id = dnsrr["id"]
        data["dnsresource"] = dnsrr_id
        form = DNSDataForm(data=data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)


class DNSResourceRecordHandler(OperationsHandler):
    """Manage dnsresourcerecord."""

    api_doc_section_name = "DNSResourceRecord"
    create = None
    model = DNSData
    fields = DISPLAYED_DNSDATA_FIELDS

    @classmethod
    def resource_uri(cls, dnsresourcerecord=None):
        # See the comment in NodeHandler.resource_uri.
        dnsresourcerecord_id = "id"
        if dnsresourcerecord is not None:
            dnsresourcerecord_id = dnsresourcerecord.id
        return ("dnsresourcerecord_handler", (dnsresourcerecord_id,))

    @classmethod
    def name(cls, dnsresourcerecord):
        """Return the name of the dnsresourcerecord."""
        return dnsresourcerecord.fqdn()

    def read(self, request, id):
        """@description-title Read a DNS resource record
        description Read a DNS resource record with the given id.

        @param (int) "{id}" [required=true] The DNS resource record id.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the requested
        DNS resource object.
        @success-example "success-json" [exkey=dnsresourcerecords-read-by-id]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested DNS resource record was not
        found.
        @error-example "not-found"
            No DNSData matches the given query.
        """
        return DNSData.objects.get_dnsdata_or_404(
            id, request.user, NodePermission.view
        )

    def update(self, request, id):
        """@description-title Update a DNS resource record
        @description Update a DNS resource record with the given id.

        @param (int) "{id}" [required=true] The DNS resource record id.

        @param (string) "rrtype" [required=false] Resource type.

        @param (string) "rrdata" [required=false] Resource data (everything to
        the right of type.)

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the updated DNS
        resource record object.
        @success-example "success-json" [exkey=dnsresourcerecords-update]
        placeholder text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to update
        the requested DNS resource record.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested DNS resource record is not
        found.
        @error-example "not-found"
            No DNSData matches the given query.
        """
        dnsdata = DNSData.objects.get_dnsdata_or_404(
            id, request.user, NodePermission.admin
        )
        data = request.data.copy()
        data["dnsresource"] = dnsdata.dnsresource.id
        form = DNSDataForm(instance=dnsdata, data=data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, id):
        """@description-title Delete a DNS resource record
        @description Delete a DNS resource record with the given id.

        @param (int) "{id}" [required=true] The DNS resource record id.

        @success (http-status-code) "server-success" 204

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to delete
        the requested DNS resource record.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested DNS resource record is not
        found.
        @error-example "not-found"
            No DNSData matches the given query.
        """
        dnsdata = DNSData.objects.get_dnsdata_or_404(
            id, request.user, NodePermission.admin
        )
        dnsrr = dnsdata.dnsresource
        dnsdata.delete()
        if not dnsrr.dnsdata_set.exists() and not dnsrr.ip_addresses.exists():
            dnsrr.delete()
        return rc.DELETED
