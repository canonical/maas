# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Describe the architectures which a cluster controller supports."""


from collections import OrderedDict

from maasserver.clusterrpc.utils import call_clusters
from provisioningserver.rpc import cluster


def list_supported_architectures():
    """List the architecture choices supported by this cluster controller.

    These are all architectures that the cluster controller could conceivably
    deal with, regardless of whether the controller has images for them.

    :return: An :class:`OrderedDict` of choices.
    """
    results = call_clusters(cluster.ListSupportedArchitectures)
    all_arches = []
    for result in results:
        all_arches += [
            (arch["name"], arch["description"])
            for arch in result["architectures"]
        ]
    return OrderedDict(sorted(all_arches))
