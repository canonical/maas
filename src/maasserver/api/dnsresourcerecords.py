# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `DNSData`."""

from maasserver.api.support import (
    admin_method,
    OperationsHandler,
)
from maasserver.exceptions import (
    MAASAPIBadRequest,
    MAASAPIValidationError,
)
from maasserver.forms.dnsdata import DNSDataForm
from maasserver.forms.dnsresource import DNSResourceForm
from maasserver.models import (
    DNSData,
    DNSResource,
    Domain,
)
from maasserver.models.dnsresource import separate_fqdn
from maasserver.permissions import NodePermission
from piston3.utils import rc


DISPLAYED_DNSDATA_FIELDS = (
    'id',
    'fqdn',
    'ttl',
    'rrtype',
    'rrdata'
)


class DNSResourceRecordsHandler(OperationsHandler):
    """Manage DNS resource records (e.g. CNAME, MX, NS, SRV, TXT)"""
    api_doc_section_name = "DNSResourceRecords"
    update = delete = None

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ('dnsresourcerecords_handler', [])

    def read(self, request):
        """List all dnsresourcerecords.

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
                    domainname, user=request.user, perm=NodePermission.view)
            else:
                domain = Domain.objects.get_domain_or_404(
                    "name:%s" % domainname, user=request.user,
                    perm=NodePermission.view)
            query = DNSData.objects.filter(
                dnsresource__domain_id=domain.id).order_by(
                'dnsresource__name')
        else:
            query = DNSData.objects.all().order_by(
                'dnsresource__domain_id', 'dnsresource__name')
        if name is not None:
            query = query.filter(dnsresource__name=name)
        if rrtype is not None:
            query = query.filter(rrtype=rrtype)
        return query

    @admin_method
    def create(self, request):
        """Create a DNS resource record.

        :param fqdn: Hostname (with domain) for the dnsresource.  Either fqdn
            or (name, domain) must be specified.  Fqdn is ignored if either
            name or domain is given (e.g. www.your-maas.maas).
        :param name: The name (or hostname without a domain) of the DNS
            resource record (e.g. www.your-maas)
        :param domain: The domain (name or id) where to create the DNS
            resource record (Domain (e.g. 'maas')
        :param rrtype: The resource record type (e.g 'cname', 'mx', 'ns',
            'srv', 'sshfp', 'txt')
        :param rrdata: The resource record data (e.g. 'your-maas',
            '10 mail.your-maas.maas')
        """
        data = request.data.copy()
        domain = None
        fqdn = data.get('fqdn', None)
        name = data.get('name', None)
        domainname = data.get('domain', None)
        rrtype = data.get('rrtype', None)
        rrdata = data.get('rrdata', None)
        if rrtype is None:
            raise MAASAPIBadRequest("rrtype must be provided.")
        if rrdata is None:
            raise MAASAPIBadRequest("rrdata must be provided.")
        # If the user gave us fqdn and did not give us name/domain, expand
        # fqdn.
        if domainname is None and name is None and fqdn is not None:
            # We need a type for resource separation.  If the user didn't give
            # us a rrtype, then assume it's an address of some sort.
            rrtype = data.get('rrtype', None)
            (name, domainname) = separate_fqdn(fqdn, rrtype)
            data['domain'] = domainname
            data['name'] = name
        # If the domain is a name, make it an id.
        if domainname is not None:
            if domainname.isdigit():
                domain = Domain.objects.get_domain_or_404(
                    domainname, user=request.user, perm=NodePermission.view)
            else:
                domain = Domain.objects.get_domain_or_404(
                    "name:%s" % domainname, user=request.user,
                    perm=NodePermission.view)
            data['domain'] = domain.id
        if domain is None or name is None:
            raise MAASAPIValidationError(
                "Either name and domain (or fqdn) must be specified")
        # Do we already have a DNSResource for this fqdn?
        dnsrr = DNSResource.objects.filter(name=name, domain__id=domain.id)
        if not dnsrr.exists():
            form = DNSResourceForm(data=data, request=request)
            if form.is_valid():
                form.save()
            else:
                raise MAASAPIValidationError(form.errors)
            dnsrr = DNSResource.objects.filter(name=name, domain__id=domain.id)
        data['dnsresource'] = dnsrr
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
        return ('dnsresourcerecord_handler', (dnsresourcerecord_id,))

    @classmethod
    def name(cls, dnsresourcerecord):
        """Return the name of the dnsresourcerecord."""
        return dnsresourcerecord.fqdn()

    def read(self, request, id):
        """Read dnsresourcerecord.

        Returns 404 if the dnsresourcerecord is not found.
        """
        return DNSData.objects.get_dnsdata_or_404(
            id, request.user, NodePermission.view)

    def update(self, request, id):
        """Update dnsresourcerecord.

        :param rrtype: Resource Type
        :param rrdata: Resource Data (everything to the right of Type.)

        Returns 403 if the user does not have permission to update the
        dnsresourcerecord.
        Returns 404 if the dnsresourcerecord is not found.
        """
        dnsdata = DNSData.objects.get_dnsdata_or_404(
            id, request.user, NodePermission.admin)
        data = request.data.copy()
        data['dnsresource'] = dnsdata.dnsresource.id
        form = DNSDataForm(instance=dnsdata, data=data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, id):
        """Delete dnsresourcerecord.

        Returns 403 if the user does not have permission to delete the
        dnsresourcerecord.
        Returns 404 if the dnsresourcerecord is not found.
        """
        dnsdata = DNSData.objects.get_dnsdata_or_404(
            id, request.user, NodePermission.admin)
        dnsrr = dnsdata.dnsresource
        dnsdata.delete()
        if dnsrr.dnsdata_set.count() == 0 and dnsrr.ip_addresses.count() == 0:
            dnsrr.delete()
        return rc.DELETED
