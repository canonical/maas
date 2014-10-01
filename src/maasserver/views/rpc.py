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


def info(request):
    """View returning a JSON document with information about RPC endpoints.

    Currently the only information returned is a list of `(host, port)` tuples
    on which the region has listening RPC endpoints.

    When the `rpc-advertise` service is not running this returns `None`
    instead of the list of event-loop endpoints. This denotes something along
    the lines of "I don't know". The cluster should not act on this, and
    instead ask again later.

    """
    try:
        advertiser = eventloop.services.getServiceNamed("rpc-advertise")
    except KeyError:
        # RPC advertising service has not been created, so we declare
        # that there are no endpoints *at all*.
        endpoints = None
    else:
        if advertiser.running:
            endpoints = {}
            for name, addr, port in advertiser.dump():
                if name in endpoints:
                    endpoints[name].append((addr, port))
                else:
                    endpoints[name] = [(addr, port)]
        else:
            # RPC advertising service is not running, so we declare that
            # there are no endpoints *at all*.
            endpoints = None

    # Each endpoint is an entry point into this event-loop.
    info = {"eventloops": endpoints}

    return HttpResponse(json.dumps(info), content_type="application/json")
