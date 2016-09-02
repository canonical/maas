# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Discovery`."""

__all__ = [
    'DiscoveryHandler',
    'DiscoveriesHandler',
    ]

from maasserver.api.support import (
    operation,
    OperationsHandler,
)
from maasserver.models import Discovery


DISPLAYED_DISCOVERY_FIELDS = (
    'discovery_id',
    'ip',
    'mac_address',
    'mac_organization',
    'last_seen',
    'hostname',
    'fabric_name',
    'vid',
    'observer',
)


class DiscoveryHandler(OperationsHandler):
    """Read or delete an observed discovery."""
    api_doc_section_name = "Discovery"
    # This is a view-backed, read-only API.
    create = delete = update = None
    fields = DISPLAYED_DISCOVERY_FIELDS
    model = Discovery

    @classmethod
    def resource_uri(cls, discovery=None):
        # See the comment in NodeHandler.resource_uri.
        discovery_id = "discovery_id"
        if discovery is not None:
            # discovery_id = quote_url(discovery.discovery_id)
            discovery_id = discovery.discovery_id
        return ('discovery_handler', (discovery_id,))

    def read(self, request, **kwargs):
        discovery_id = kwargs.get('discovery_id', None)
        discovery = Discovery.objects.get_discovery_or_404(discovery_id)
        return discovery

    @classmethod
    def observer(cls, discovery):
        return {
            'system_id': discovery.observer_system_id,
            'hostname': discovery.observer_hostname,
            'interface_id': discovery.observer_interface_id,
            'interface_name': discovery.observer_interface_name,
        }


class DiscoveriesHandler(OperationsHandler):
    """Query observed discoveries."""
    api_doc_section_name = "Discoveries"
    # This is a view-backed, read-only API.
    create = update = delete = None

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('discoveries_handler', [])

    def read(self, request, **kwargs):
        return Discovery.objects.all().order_by("-last_seen")

    @operation(idempotent=True)
    def by_unknown_mac(self, request, **kwargs):
        return Discovery.objects.by_unknown_mac().order_by("-last_seen")

    @operation(idempotent=True)
    def by_unknown_ip(self, request, **kwargs):
        return Discovery.objects.by_unknown_ip().order_by("-last_seen")

    @operation(idempotent=True)
    def by_unknown_ip_and_mac(self, request, **kwargs):
        return Discovery.objects.by_unknown_ip_and_mac().order_by("-last_seen")
