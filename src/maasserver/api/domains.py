# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Domain`."""

from maasserver.api.support import (
    admin_method,
    AnonymousOperationsHandler,
    operation,
    OperationsHandler,
)
from maasserver.dns.config import dns_force_reload
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms.domain import DomainForm
from maasserver.models import (
    Domain,
    GlobalDefault,
)
from maasserver.models.dnspublication import zone_serial
from maasserver.permissions import NodePermission
from maasserver.sequence import INT_MAX
from piston3.utils import rc


DISPLAYED_DOMAIN_FIELDS = (
    'id',
    'name',
    'ttl',
    'authoritative',
    'resource_record_count',
    'is_default',
)


class DomainsHandler(OperationsHandler):
    """Manage domains."""
    api_doc_section_name = "Domains"
    update = delete = None
    fields = DISPLAYED_DOMAIN_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ('domains_handler', [])

    def read(self, request):
        """List all domains."""
        return Domain.objects.all().prefetch_related('globaldefault_set')

    @admin_method
    def create(self, request):
        """Create a domain.

        :param name: Name of the domain.
        :param authoritative: Class type of the domain.
        """
        form = DomainForm(data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    @admin_method
    @operation(idempotent=False)
    def set_serial(self, request):
        """Set the SOA serial number (for all DNS zones.)

        :param serial: serial number to use next.
        """
        try:
            serial = int(request.data['serial'])
        except KeyError:
            raise MAASAPIValidationError(
                {'serial': 'Missing parameter'})
        except ValueError:
            raise MAASAPIValidationError(
                {'serial': 'Expected a serial number'})
        if serial == 0 or serial > INT_MAX:
            raise MAASAPIValidationError(
                {'serial':
                    'Expected a serial number between 1 and %d' % INT_MAX})
        zone_serial.set_value(serial)
        dns_force_reload()


class AnonDomainHandler(AnonymousOperationsHandler):
    """Anonymous access to domain."""
    read = create = update = delete = None
    model = Domain
    fields = DISPLAYED_DOMAIN_FIELDS


class DomainHandler(OperationsHandler):
    """Manage domain."""
    api_doc_section_name = "Domain"
    create = None
    model = Domain
    fields = DISPLAYED_DOMAIN_FIELDS

    @classmethod
    def resource_uri(cls, domain=None):
        # See the comment in NodeHandler.resource_uri.
        domain_id = "id"
        if domain is not None:
            domain_id = domain.id
        return ('domain_handler', (domain_id,))

    @classmethod
    def name(cls, domain):
        """Return the name of the domain."""
        return domain.get_name()

    @classmethod
    def is_default(cls, domain):
        """Returns True if the domain is a default domain."""
        return domain.is_default()

    @classmethod
    def resources(cls, domain):
        """Return DNSResources within the specified domain."""
        return domain.dnsresource_set.all()

    def read(self, request, id):
        """Read domain.

        Returns 404 if the domain is not found.
        """
        return Domain.objects.get_domain_or_404(
            id, request.user, NodePermission.view)

    def update(self, request, id):
        """Update domain.

        :param name: Name of the domain.
        :param authoritative: True if we are authoritative for this domain.
        :param ttl: The default TTL for this domain.

        Returns 403 if the user does not have permission to update the
        dnsresource.
        Returns 404 if the domain is not found.
        """
        domain = Domain.objects.get_domain_or_404(
            id, request.user, NodePermission.admin)
        form = DomainForm(instance=domain, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False)
    def set_default(self, request, id):
        """Set the specified domain to be the default.

        If any unallocated nodes are using the previous default domain,
        changes them to use the new default domain.

        Returns 403 if the user does not have permission to update the
        default domain.
        Returns 404 if the domain is not found.
        """
        domain = Domain.objects.get_domain_or_404(
            id, request.user, NodePermission.admin)
        global_defaults = GlobalDefault.objects.instance()
        global_defaults.domain = domain
        global_defaults.save()
        return domain

    def delete(self, request, id):
        """Delete domain.

        Returns 403 if the user does not have permission to update the
        domain.
        Returns 404 if the domain is not found.
        """
        domain = Domain.objects.get_domain_or_404(
            id, request.user, NodePermission.admin)
        domain.delete()
        return rc.DELETED
