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
        queryset = Domain.objects.all()
        pk = 'id'
        allowed_methods = ['list', 'get', 'set_active']
        listen_channels = [
            "domain",
            ]

    def dehydrate(self, domain, data, for_list=False):
        ip_addresses, ipcount = domain.render_json_for_related_ips(for_list)
        rrsets, rrcount = domain.render_json_for_related_rrdata(for_list)
        if not for_list:
            data["ip_addresses"] = ip_addresses
            data["rrsets"] = rrsets
        data["resource_count"] = ipcount + rrcount
        return data
