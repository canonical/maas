# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver RPC views."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import json

from django.core.urlresolvers import reverse
from maasserver import eventloop
from maasserver.testing.testcase import MAASServerTestCase
from provisioningserver.utils import get_all_interface_addresses
from testtools.matchers import (
    Equals,
    GreaterThan,
    IsInstance,
    KeysEqual,
    LessThan,
    MatchesAll,
    MatchesDict,
    MatchesListwise,
    )


is_valid_port = MatchesAll(
    IsInstance(int), GreaterThan(0), LessThan(2 ** 16))


class RPCViewTest(MAASServerTestCase):

    def test_rpc_info(self):
        response = self.client.get(reverse('rpc-info'))
        self.assertEqual("application/json", response["Content-Type"])
        info = json.loads(response.content)
        self.assertEqual({"eventloops": {}}, info)

    def test_rpc_info_when_rpc_running(self):
        eventloop.start()
        self.addCleanup(eventloop.stop)

        response = self.client.get(reverse('rpc-info'))
        self.assertEqual("application/json", response["Content-Type"])
        info = json.loads(response.content)
        self.assertThat(info, KeysEqual("eventloops"))
        self.assertThat(info["eventloops"], MatchesDict({
            # Each entry in the endpoints dict is a mapping from an
            # event loop to a list of (host, port) tuples. Each tuple is
            # a potential endpoint for connecting into that event loop.
            eventloop.loop.name: MatchesListwise([
                MatchesListwise((Equals(addr), is_valid_port))
                for addr in get_all_interface_addresses()
            ]),
        }))
