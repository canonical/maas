# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Stats related utility functions."""

import base64
from collections import Counter
import json

from maasserver.enum import NODE_TYPE
from maasserver.models import Node
from maasserver.utils import get_maas_user_agent
import requests


def get_maas_stats():
    node_types = Node.objects.values_list('node_type', flat=True)
    node_types = Counter(node_types)

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
        }
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
