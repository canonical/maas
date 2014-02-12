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
import maasserver.views.rpc
from maastesting.factory import factory
from testtools.matchers import (
    GreaterThan,
    HasLength,
    IsInstance,
    KeysEqual,
    LessThan,
    MatchesAll,
    )


class RPCViewTest(MAASServerTestCase):

    def test_rpc_info(self):
        response = self.client.get(reverse('rpc-info'))
        self.assertEqual("application/json", response["Content-Type"])
        info = json.loads(response.content)
        self.assertEqual({"endpoints": []}, info)

    def test_rpc_info_when_rpc_running(self):
        eventloop.start()
        self.addCleanup(eventloop.stop)

        example_host = factory.make_hostname()
        get_maas_facing_server_address = self.patch(
            maasserver.views.rpc, "get_maas_facing_server_address")
        get_maas_facing_server_address.return_value = example_host

        response = self.client.get(reverse('rpc-info'))
        self.assertEqual("application/json", response["Content-Type"])
        info = json.loads(response.content)
        self.assertThat(info, KeysEqual("endpoints"))
        self.assertThat(info["endpoints"], MatchesAll(
            IsInstance(list), HasLength(1)))
        [endpoint] = info["endpoints"]
        self.assertThat(endpoint, HasLength(2))
        host, port = endpoint
        self.assertEqual(host, example_host)
        self.assertThat(port, MatchesAll(
            IsInstance(int), GreaterThan(0), LessThan(2 ** 16)))
