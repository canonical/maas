# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Domain`."""

from piston3.utils import rc

from maasserver.api.support import (
    admin_method,
    AnonymousOperationsHandler,
    operation,
    OperationsHandler,
)
from maasserver.dns.config import dns_force_reload
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms.domain import DomainForm
from maasserver.models import Domain, GlobalDefault
from maasserver.models.dnspublication import zone_serial
from maasserver.permissions import NodePermission
from maasserver.sequence import INT_MAX

DISPLAYED_DOMAIN_FIELDS = (
    "id",
    "name",
    "ttl",
    "authoritative",
    "resource_record_count",
    "is_default",
)


class DomainsHandler(OperationsHandler):
    """Manage domains."""

    api_doc_section_name = "Domains"
    update = delete = None
    fields = DISPLAYED_DOMAIN_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ("domains_handler", [])

    def read(self, request):
        """@description-title List all domains
        @description List all domains.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a list of
        domain objects.
        @success-example "success-json" [exkey=domains-read] placeholder text
        """
        return Domain.objects.all().prefetch_related("globaldefault_set")

    @admin_method
    def create(self, request):
        """@description-title Create a domain
        @description Create a domain.

        @param (string) "name" [required=true] Name of the domain.

        @param (string) "authoritative" [required=false] Class type of the
        domain.

        @param (string) "forward_dns_servers" [required=false] List of forward dns
        server IP addresses when MAAS is not authorititative.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the new domain
        object.
        @success-example "success-json" [exkey=domains-create] placeholder text
        """
        form = DomainForm(data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    @admin_method
    @operation(idempotent=False)
    def set_serial(self, request):
        """@description-title Set the SOA serial number
        @description Set the SOA serial number for all DNS zones.

        @param (int) "serial" [required=true] Serial number to use next.

        @success (http-status-code) "server-success" 200
        @success (content) "success-text" No content returned.
        """
        try:
            serial = int(request.data["serial"])
        except KeyError:
            raise MAASAPIValidationError({"serial": "Missing parameter"})  # noqa: B904
        except ValueError:
            raise MAASAPIValidationError(  # noqa: B904
                {"serial": "Expected a serial number"}
            )
        if serial == 0 or serial > INT_MAX:
            raise MAASAPIValidationError(
                {
                    "serial": "Expected a serial number between 1 and %d"
                    % INT_MAX
                }
            )
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
        return ("domain_handler", (domain_id,))

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
        """@description-title Read domain
        @description Read a domain with the given id.

        @param (int) "{id}" [required=true] A domain id.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing
        information about the requsted domain.
        @success-example "success-json" [exkey=domains-read] placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested domain is not found.
        @error-example "not-found"
            No Domain matches the given query.
        """
        return Domain.objects.get_domain_or_404(
            id, request.user, NodePermission.view
        )

    def update(self, request, id):
        """@description-title Update a domain
        @description Update a domain with the given id.

        @param (int) "{id}" [required=true] A domain id.

        @param (string) "name" [required=true] Name of the domain.

        @param (string) "authoritative" [required=false] True if we are
        authoritative for this domain.

        @param (string) "ttl" [required=false] The default TTL for this domain.

        @param (string) "forward_dns_servers" [required=false] List of IP addresses for
        forward DNS servers when MAAS is not authoritative for this domain.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing
        information about the updated domain.
        @success-example "success-json" [exkey=domains-update] placeholder text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have the permissions
        required to update the domain.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested domain name is not found.
        @error-example "not-found"
            No Domain matches the given query.
        """
        domain = Domain.objects.get_domain_or_404(
            id, request.user, NodePermission.admin
        )
        form = DomainForm(instance=domain, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False)
    def set_default(self, request, id):
        """@description-title Set domain as default
        @description Set the specified domain to be the default.

        @param (int) "{id}" [required=true] A domain id.

        If any unallocated nodes are using the previous default domain,
        changes them to use the new default domain.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing
        information about the updated domain.
        @success-example "success-json" [exkey=domains-set-default] placeholder
        text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have the permissions
        required to update the domain.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested domain name is not found.
        @error-example "not-found"
            No Domain matches the given query.
        """
        domain = Domain.objects.get_domain_or_404(
            id, request.user, NodePermission.admin
        )
        global_defaults = GlobalDefault.objects.instance()
        global_defaults.domain = domain
        global_defaults.save()
        return domain

    def delete(self, request, id):
        """@description-title Delete domain
        @description Delete a domain with the given id.

        @param (int) "{id}" [required=true] A domain id.

        @success (http-status-code) "server-success" 204

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have the permissions
        required to update the domain.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested domain name is not found.
        @error-example "not-found"
            No Domain matches the given query.
        """
        domain = Domain.objects.get_domain_or_404(
            id, request.user, NodePermission.admin
        )
        domain.delete()
        return rc.DELETED
