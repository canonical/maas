# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Views relating to the region<-->cluster RPC mechanism.

Each region controller process starts its own RPC endpoint, and this
provides the means for clusters to discover what they are.
"""


import json

from django.http import HttpResponse

from maasserver.models.node import RegionController


def get_endpoints():
    """Returns a list of ``(name, addr, port)`` tuples.

    Each tuple corresponds to somewhere an event-loop is listening
    within the whole region. The `name` is the event-loop name.
    """

    # Each regiond might be running a local bridge that duplicates the
    # same IP address across region controllers. Each region controller
    # must output a set of unique of IP addresses, to prevent the rack
    # controller from connecting to a different region controller then
    # the rack controller was expecting to be connecting to.
    def _unique_to_region(address, region, regions):
        for region_obj in regions:
            if region_obj != region:
                for process in region_obj.processes.all():
                    for endpoint in process.endpoints.all():
                        if endpoint.address == address:
                            return False
        return True

    regions = RegionController.objects.all()
    regions = regions.prefetch_related("processes", "processes__endpoints")
    all_endpoints = []
    for region_obj in regions:
        for process in region_obj.processes.all():
            for endpoint in process.endpoints.all():
                if _unique_to_region(endpoint.address, region_obj, regions):
                    all_endpoints.append(
                        (
                            "%s:pid=%d" % (region_obj.hostname, process.pid),
                            endpoint.address,
                            endpoint.port,
                        )
                    )
    return all_endpoints


def info(request):
    """View returning a JSON document with information about RPC endpoints.

    Currently the only information returned is a list of `(host, port)` tuples
    on which the region has listening RPC endpoints.

    When the `rpc-advertise` service is not running this returns `None`
    instead of the list of event-loop endpoints. This denotes something along
    the lines of "I don't know". The cluster should not act on this, and
    instead ask again later.

    """
    endpoints = {}
    for name, addr, port in get_endpoints():
        if name in endpoints:
            endpoints[name].append((addr, port))
        else:
            endpoints[name] = [(addr, port)]

    # Each endpoint is an entry point into this event-loop.
    info = {"eventloops": endpoints}

    return HttpResponse(json.dumps(info), content_type="application/json")
