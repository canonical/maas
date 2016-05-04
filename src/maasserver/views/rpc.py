# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Views relating to the region<-->cluster RPC mechanism.

Each region controller process starts its own RPC endpoint, and this
provides the means for clusters to discover what they are.
"""

__all__ = [
    "info",
]

import json

from django.http import HttpResponse
from maasserver import eventloop
from provisioningserver.utils.twisted import (
    asynchronous,
    FOREVER,
)


def info(request):
    """View returning a JSON document with information about RPC endpoints.

    Currently the only information returned is a list of `(host, port)` tuples
    on which the region has listening RPC endpoints.

    When the `rpc-advertise` service is not running this returns `None`
    instead of the list of event-loop endpoints. This denotes something along
    the lines of "I don't know". The cluster should not act on this, and
    instead ask again later.

    """
    advertising = _getAdvertisingInstance()
    if advertising is None:
        # RPC advertising service is not running, so we declare that there are
        # no endpoints *at all*.
        endpoints = None
    else:
        endpoints = {}
        for name, addr, port in advertising.dump():
            if name in endpoints:
                endpoints[name].append((addr, port))
            else:
                endpoints[name] = [(addr, port)]

    # Each endpoint is an entry point into this event-loop.
    info = {"eventloops": endpoints}

    return HttpResponse(json.dumps(info), content_type="application/json")


@asynchronous(timeout=FOREVER)
def _getAdvertisingInstance():
    """Return the currently active :class:`RegionAdvertising` instance.

    Or `None` if the RPC advertising service is not running, has failed to
    start-up, or takes too long to start.
    """
    try:
        advertiser = eventloop.services.getServiceNamed("rpc-advertise")
    except KeyError:
        # The advertising service has not been created.
        return None
    else:
        if advertiser.running:
            # Wait a short time in case the advertising service is still
            # starting. Errors may arise from a failure during its start-up,
            # but suppress them here because they are logged elsewhere.
            return advertiser.advertising.get(1.0).addErrback(lambda _: None)
        else:
            # The advertising service is not running.
            return None
