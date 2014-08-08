# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Obtain OS information from clusters."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "gen_all_known_operating_systems",
    "get_preseed_data",
]

from collections import defaultdict
from functools import partial
from urlparse import urlparse

from maasserver.rpc import (
    getAllClients,
    getClientFor,
    )
from maasserver.utils import async
from provisioningserver.rpc.cluster import (
    GetPreseedData,
    ListOperatingSystems,
    )
from provisioningserver.utils.twisted import synchronous
from twisted.python.failure import Failure


def suppress_failures(responses):
    """Suppress failures returning from an async/gather operation.

    This may not be advisable! Be very sure this is what you want.
    """
    for response in responses:
        if not isinstance(response, Failure):
            yield response


@synchronous
def gen_all_known_operating_systems():
    """Generator yielding details on OSes supported by any cluster.

    Each item yielded takes the same form as the ``osystems`` value from
    the :py:class:`provisioningserver.rpc.cluster.ListOperatingSystems`
    RPC command. Exactly matching duplicates are suppressed.
    """
    seen = defaultdict(list)
    responses = async.gather(
        partial(client, ListOperatingSystems)
        for client in getAllClients().wait())
    for response in suppress_failures(responses):
        for osystem in response["osystems"]:
            name = osystem["name"]
            if osystem not in seen[name]:
                seen[name].append(osystem)
                yield osystem


@synchronous
def get_preseed_data(preseed_type, node, token, metadata_url):
    """Obtain optional preseed data for this OS, preseed type, and node.

    :param preseed_type: The type of preseed to compose.
    :param node: The node model instance.
    :param token: The token model instance.
    :param metadata_url: The URL where this node's metadata will be made
        available.

    :raises NoConnectionsAvailable: When no connections to the node's
        cluster are available for use.
    :raises NoSuchOperatingSystem: When the node's declared operating
        system is not known to its cluster.
    :raises NotImplementedError: When this node's OS does not want to
        define any OS-specific preseed data.
    :raises TimeoutError: If a response has not been received within 30
        seconds.
    """
    client = getClientFor(node.nodegroup.uuid).wait(5)
    call = client(
        GetPreseedData, osystem=node.get_osystem(), preseed_type=preseed_type,
        node_system_id=node.system_id, node_hostname=node.hostname,
        consumer_key=token.consumer.key, token_key=token.key,
        token_secret=token.secret, metadata_url=urlparse(metadata_url))
    return call.wait(30)
