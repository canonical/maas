# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Common code for MAAS Cluster RPC operations."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'call_clusters',
    ]


from functools import partial

from maasserver import logger
from maasserver.exceptions import ClusterUnavailable
from maasserver.models import NodeGroup
from maasserver.rpc import getClientFor
from maasserver.utils import async
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from twisted.python.failure import Failure


def call_clusters(command, nodegroups=None, ignore_errors=True):
    """Make an RPC call to all clusters in parallel.

    :param nodegroups: The :class:`NodeGroup`s on which to make the RPC
        call. If None, defaults to all :class:`NodeGroup`s.
    :param command: An :class:`amp.Command` to call on the clusters.
    :param ignore_errors: If True, errors encountered whilst calling
        `command` on the clusters won't raise an exception.
    :return: A generator of results, i.e. the dicts returned by the RPC
        call.
    :raises: :py:class:`ClusterUnavailable` when a cluster is not
        connected or there's an error during the call, and errors are
        not being ignored.
    """
    calls = []
    if nodegroups is None:
        nodegroups = NodeGroup.objects.all()
    for ng in nodegroups:
        try:
            client = getClientFor(ng.uuid).wait()
        except NoConnectionsAvailable:
            logger.error(
                "Unable to get RPC connection for cluster '%s'", ng.name)
            if not ignore_errors:
                raise ClusterUnavailable(
                    "Unable to get RPC connection for cluster '%s'" % ng.name)
        else:
            call = partial(client, command)
            calls.append(call)

    for response in async.gather(calls, timeout=10):
        if isinstance(response, Failure):
            # XXX: How to get the cluster ID/name here?
            logger.error("Failure while communicating with cluster")
            logger.error(response.getTraceback())
            if not ignore_errors:
                raise ClusterUnavailable(
                    "Failure while communicating with cluster.")
        else:
            yield response
