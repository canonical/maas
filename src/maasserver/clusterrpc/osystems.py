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
]

from collections import defaultdict
from functools import partial

from maasserver.rpc import getAllClients
from maasserver.utils import async
from provisioningserver.rpc.cluster import ListOperatingSystems
from twisted.python.failure import Failure


def suppress_failures(responses):
    """Suppress failures returning from an async/gather operation.

    This may not be advisable! Be very sure this is what you want.
    """
    for response in responses:
        if not isinstance(response, Failure):
            yield response


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
