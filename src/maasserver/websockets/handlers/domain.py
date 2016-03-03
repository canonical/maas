# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The domain handler for the WebSocket connection."""

__all__ = [
    "DomainHandler",
    ]

from maasserver.enum import NODE_PERMISSION
from maasserver.models.domain import Domain
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)


class DomainHandler(TimestampedModelHandler):

    class Meta:
        queryset = Domain.objects.all()
        pk = 'id'
        allowed_methods = ['list', 'get', 'create', 'delete', 'set_active']
        listen_channels = [
            "domain",
            ]

    def dehydrate(self, domain, data, for_list=False):
        rrsets = domain.render_json_for_related_rrdata(for_list=for_list)
        if not for_list:
            data["rrsets"] = rrsets
        data["hosts"] = len({
            rr['system_id'] for rr in rrsets if rr['system_id'] is not None})
        data["resource_count"] = len(rrsets)
        return data

    def delete(self, parameters):
        """Delete this Domain."""
        domain = self.get_object(parameters)
        assert self.user.has_perm(
            NODE_PERMISSION.ADMIN, domain), "Permission denied."
        domain.delete()
