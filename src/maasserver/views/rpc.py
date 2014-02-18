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
from provisioningserver.utils import get_all_interface_addresses


def info(request):
    """View returning a JSON document with information about RPC endpoints.

    Currently the only information returned is a list of `(host, port)`
    tuples on which the region has listening RPC endpoints.
    """
    try:
        rpc_service = eventloop.services.getServiceNamed("rpc")
    except KeyError:
        endpoints = {}  # No endpoints.
    else:
        port = rpc_service.getPort()
        addrs = get_all_interface_addresses()
        endpoints = {
            eventloop.loop.name: [
                (addr, port) for addr in addrs
            ],
        }

    # Each endpoint is an entry point into this event-loop.
    info = {"eventloops": endpoints}

    return HttpResponse(json.dumps(info), content_type="application/json")
