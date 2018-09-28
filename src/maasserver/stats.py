# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Boot Resources."""

__all__ = [
    "StatsService",
    "STATS_SERVICE_PERIOD",
]

from datetime import timedelta

from django.db.models import Sum
from maasserver.models import Config
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.logger import LegacyLogger
from twisted.application.internet import TimerService


log = LegacyLogger()

import base64
from collections import Counter
import json

from maasserver.enum import (
    NODE_TYPE,
    NODE_STATUS,
)
from maasserver.models import (
    Node,
    Fabric,
    VLAN,
    Space,
    Subnet,
)
from maasserver.utils import get_maas_user_agent
import requests


def get_machine_stats():
    nodes = Node.objects.all()
    machines = nodes.filter(node_type=NODE_TYPE.MACHINE)
    # Rather overall amount of stats for machines.
    return machines.aggregate(
        total_cpu=Sum('cpu_count'), total_mem=Sum('memory'),
        total_storage=Sum('blockdevice__size'))


def get_machine_state_stats():
    node_status = Node.objects.values_list('status', flat=True)
    node_status = Counter(node_status)

    return {
        "ready": node_status.get(NODE_STATUS.READY, 0),
        "allocated": node_status.get(NODE_STATUS.ALLOCATED, 0),
        "deploying": node_status.get(NODE_STATUS.DEPLOYING, 0),
        "deployed": node_status.get(NODE_STATUS.DEPLOYED, 0),
        "failed_deployment": node_status.get(
            NODE_STATUS.FAILED_DEPLOYMENT, 0),
        "failed_commissioning": node_status.get(
            NODE_STATUS.FAILED_COMMISSIONING, 0),
        }


def get_subnets_stats():
    subnets = Subnet.objects.all()
    v4 = [net for net in subnets if net.get_ip_version() == 4]
    v6 = [net for net in subnets if net.get_ip_version() == 6]
    return {
        "spaces": Space.objects.count(),
        "fabrics": Fabric.objects.count(),
        "vlans": VLAN.objects.count(),
        "subnets_v4": len(v4),
        "subnets_v6": len(v6),
        }


def get_maas_stats():
    # TODO
    # - architectures
    # - resource pools
    # - pods
    # Get all node types to get count values
    node_types = Node.objects.values_list('node_type', flat=True)
    node_types = Counter(node_types)
    # get summary of machine resources, and its statuses.
    stats = get_machine_stats()
    machine_status = get_machine_state_stats()
    # get summary of network objects
    netstats = get_subnets_stats()

    return json.dumps({
        "controllers": {
            "regionracks": node_types.get(
                NODE_TYPE.REGION_AND_RACK_CONTROLLER, 0),
            "regions": node_types.get(NODE_TYPE.REGION_CONTROLLER, 0),
            "racks": node_types.get(NODE_TYPE.RACK_CONTROLLER, 0),
        },
        "nodes": {
            "machines": node_types.get(NODE_TYPE.MACHINE, 0),
            "devices": node_types.get(NODE_TYPE.DEVICE, 0),
        },
        "machine_stats": stats,
        "machine_status": machine_status,
        "network_stats": netstats,
    })


def get_request_params():
    return {
        "data": base64.b64encode(
            json.dumps(get_maas_stats()).encode()).decode(),
    }


def make_maas_user_agent_request():
    headers = {
        'User-Agent': get_maas_user_agent(),
    }
    params = get_request_params()
    try:
        requests.get(
            'https://stats.images.maas.io/',
            params=params, headers=headers)
    except:
        # Do not fail if for any reason requests does.
        pass


# How often the import service runs.
STATS_SERVICE_PERIOD = timedelta(hours=24)


class StatsService(TimerService, object):
    """Service to periodically get stats.

    This will run immediately when it's started, then once again every
    24 hours, though the interval can be overridden by passing it to
    the constructor.
    """

    def __init__(self, interval=STATS_SERVICE_PERIOD):
        super(StatsService, self).__init__(
            interval.total_seconds(), self.maybe_make_stats_request)

    def maybe_make_stats_request(self):
        def determine_stats_request():
            if Config.objects.get_config('enable_analytics'):
                make_maas_user_agent_request()

        d = deferToDatabase(transactional(determine_stats_request))
        d.addErrback(log.err, "Failure performing user agent request.")
        return d
