# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The domain handler for the WebSocket connection."""

__all__ = [
    "DomainHandler",
    ]

from maasserver.models.domain import Domain
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)


class DomainHandler(TimestampedModelHandler):

    class Meta:
        queryset = (
            Domain.objects.all()
                  .prefetch_related('node_set')
                  .prefetch_related('dnsresource_set__dnsdata_set')
                  .prefetch_related('dnsresource_set__staticipaddress_set')
                  .prefetch_related('node_set__staticipaddress_set'))
        pk = 'id'
        allowed_methods = ['list', 'get', 'set_active']
        listen_channels = [
            "domain",
            ]

    def dehydrate(self, domain, data, for_list=False):
        if not for_list:
            data["ip_addresses"] = domain.render_json_for_related_ips()
            data["rrsets"] = domain.render_json_for_related_rrdata()
        return data
