# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The subnet handler for the WebSocket connection."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )


str = None

__metaclass__ = type
__all__ = [
    "SubnetHandler",
    ]

from maasserver.models.subnet import Subnet
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)
from provisioningserver.utils.network import IPRangeStatistics


class SubnetHandler(TimestampedModelHandler):

    class Meta:
        queryset = (
            Subnet.objects.all()
                  .select_related('space')
                  .prefetch_related('nodegroupinterface_set__nodegroup')
                  .prefetch_related('staticipaddress_set__user')
                  .prefetch_related(
                      'staticipaddress_set__user__interface_set__node'))
        pk = 'id'
        allowed_methods = ['list', 'get', 'set_active']
        listen_channels = [
            "subnet",
            ]

    def dehydrate(self, subnet, data, for_list=False):
        if not for_list:
            full_range = subnet.get_iprange_usage()
            metadata = IPRangeStatistics(full_range)
            data['statistics'] = metadata.render_json()
            data["ip_addresses"] = subnet.render_json_for_related_ips(
                with_username=True, with_node_summary=True)
        return data
