# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Views relating to the region<-->cluster RPC mechanism.

Each region controller process starts its own RPC endpoint, and this
provides the means for clusters to discover what they are.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "info",
]

import json

from django.http import HttpResponse
from maasserver import eventloop
from maasserver.models import NodeGroup
from maasserver.server_address import get_maas_facing_server_address
from maasserver.utils.orm import get_one


def info(request):
    """View returning a JSON document with information about RPC endpoints.

    Currently the only information returned is a list of `(host, port)`
    tuples on which the region has listening RPC endpoints.
    """
    uuid = request.GET.get('uuid', None)
    if uuid is None:
        nodegroup = None
    else:
        nodegroup = get_one(NodeGroup.objects.filter(uuid=uuid))

    endpoints = []
    info = {"endpoints": endpoints}

    try:
        rpc_service = eventloop.services.getServiceNamed("rpc")
    except KeyError:
        pass  # No endpoints.
    else:
        hostname = get_maas_facing_server_address(nodegroup)
        endpoints.append((hostname, rpc_service.getPort()))

    return HttpResponse(json.dumps(info), content_type="application/json")
