# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The subnet handler for the WebSocket connection."""

__all__ = [
    "SubnetHandler",
    ]

from maasserver.enum import NODE_PERMISSION
from maasserver.forms_subnet import SubnetForm
from maasserver.models.subnet import Subnet
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)
from netaddr import IPNetwork
from provisioningserver.utils.network import IPRangeStatistics


class SubnetHandler(TimestampedModelHandler):

    class Meta:
        queryset = (
            Subnet.objects.all()
                  .select_related('space', 'vlan')
                  .prefetch_related('vlan__fabric')
                  .prefetch_related('staticipaddress_set__user')
                  .prefetch_related(
                      'staticipaddress_set__interface_set__node'))
        pk = 'id'
        form = SubnetForm
        form_requires_request = False
        allowed_methods = [
            'create',
            'update',
            'delete',
            'get',
            'list',
            'set_active'
        ]
        listen_channels = [
            "subnet",
        ]

    def dehydrate_dns_servers(self, dns_servers):
        if dns_servers is None:
            return ""
        return " ".join(sorted(dns_servers))

    def dehydrate(self, subnet, data, for_list=False):
        full_range = subnet.get_iprange_usage()
        metadata = IPRangeStatistics(full_range)
        data['statistics'] = metadata.render_json(
            include_ranges=True, include_suggestions=True)
        data['version'] = IPNetwork(subnet.cidr).version
        if not for_list:
            data["ip_addresses"] = subnet.render_json_for_related_ips(
                with_username=True, with_node_summary=True)
        return data

    def delete(self, parameters):
        """Delete this Subnet."""
        subnet = self.get_object(parameters)
        assert self.user.has_perm(
            NODE_PERMISSION.ADMIN, subnet), "Permission denied."
        subnet.delete()
