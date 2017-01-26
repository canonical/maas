# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The subnet handler for the WebSocket connection."""

__all__ = [
    "SubnetHandler",
    ]

from maasserver.enum import NODE_PERMISSION
from maasserver.forms_subnet import SubnetForm
from maasserver.models import (
    Discovery,
    RackController,
    Subnet,
)
from maasserver.utils.orm import reload_object
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)
from netaddr import IPNetwork
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils.network import IPRangeStatistics


maaslog = get_maas_logger("subnet")


class SubnetHandler(TimestampedModelHandler):

    class Meta:
        queryset = (
            Subnet.objects.all()
                  .select_related('vlan')
                  .select_related('vlan__space')
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
            'set_active',
            'scan',
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
        data['space'] = subnet.vlan.space_id
        if not for_list:
            data["ip_addresses"] = subnet.render_json_for_related_ips(
                with_username=True, with_node_summary=True)
        return data

    def update(self, parameters):
        subnet = self.get_object(parameters)
        assert self.user.has_perm(
            NODE_PERMISSION.ADMIN, subnet), "Permission denied."
        # The JavaScript object will still contain the space for backward
        # compatibility, so we need to strip it out.
        if 'space' in parameters:
            del parameters['space']
        return super().update(parameters)

    def delete(self, parameters):
        """Delete this Subnet."""
        subnet = self.get_object(parameters)
        assert self.user.has_perm(
            NODE_PERMISSION.ADMIN, subnet), "Permission denied."
        subnet.delete()

    def scan(self, parameters):
        """Scan the subnet for connected neighbours.

        :return: user-friendly scan results (as defined by the
            `user_friendly_scan_results()` function).
        """
        # Circular imports.
        from maasserver.api.discoveries import (
            scan_all_rack_networks,
            user_friendly_scan_results,
        )
        subnet = self.get_object(parameters)
        self.user = reload_object(self.user)
        assert self.user.has_perm(
            NODE_PERMISSION.ADMIN, Discovery), "Permission denied."
        cidr = subnet.get_ipnetwork()
        if cidr.version != 4:
            raise ValueError(
                "Cannot scan subnet: only IPv4 subnets can be scanned.")
        cidrs = [cidr]
        if RackController.objects.filter_by_subnet_cidrs(cidrs).count() == 0:
            raise ValueError("Subnet must be configured on a rack controller.")
        rpc_results = scan_all_rack_networks(cidrs=[cidr])
        maaslog.info(
            "User '%s' initiated a neighbour discovery scan against subnet: "
            "%s" % (self.user.username, cidr))
        return user_friendly_scan_results(rpc_results)
