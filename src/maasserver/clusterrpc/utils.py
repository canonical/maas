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
    'get_error_message_for_exception',
    ]


from functools import partial

from maasserver import logger
from maasserver.enum import NODEGROUP_STATUS
from maasserver.exceptions import ClusterUnavailable
from maasserver.models import NodeGroup
from maasserver.rpc import getClientFor
from maasserver.utils import async
from provisioningserver.rpc.exceptions import (
    MultipleFailures,
    NoConnectionsAvailable,
    )
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
        nodegroups = NodeGroup.objects.filter(
            status=NODEGROUP_STATUS.ACCEPTED)
    for ng in nodegroups:
        try:
            client = getClientFor(ng.uuid)
        except NoConnectionsAvailable:
            logger.error(
                "Unable to get RPC connection for cluster '%s' (%s)",
                ng.cluster_name, ng.uuid)
            if not ignore_errors:
                raise ClusterUnavailable(
                    "Unable to get RPC connection for cluster '%s' (%s)"
                    % (ng.cluster_name, ng.uuid))
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


def get_error_message_for_exception(exception):
    """Return an error message for an exception.

    If `exception` is a NoConnectionsAvailable error,
    get_error_message_for_exception() will check to see if there's a
    UUID listed. If so, this is an error referring to a cluster.
    get_error_message_for_exception() will return an error message
    containing the cluster's name (as opposed to its UUID), which is
    more useful to users.

    If `exception` is an instance of `MultipleFailures` a single error
    message will be returned, explaining where to look for more
    information.

    Otherwise, if the exception has a message attached, return that.
    If not, create meaningful error message for the exception and
    return that instead.
    """
    # If we've gt a NoConnectionsAvailable error, check it for a UUID
    # field. If it's got one, we can report the cluster details more
    # helpfully.
    is_no_connections_error = isinstance(
        exception, NoConnectionsAvailable)
    has_uuid_field = getattr(exception, 'uuid', None) is not None
    if (is_no_connections_error and has_uuid_field):
        cluster = NodeGroup.objects.get_by_natural_key(
            exception.uuid)
        return (
            "Unable to connect to cluster '%s' (%s); no connections "
            "available." % (cluster.cluster_name, cluster.uuid))

    if isinstance(exception, MultipleFailures):
        return (
            "Multiple failures encountered. See /var/log/maas/regiond.log "
            "on the region server for more information.")

    error_message = unicode(exception)
    if len(error_message) == 0:
        error_message = (
            "Unexpected exception: %s. See /var/log/maas/regiond.log "
            "on the region server for more information." %
            exception.__class__.__name__)
    return error_message
