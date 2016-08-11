# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver RPC views."""

__all__ = []

import json

from crochet import wait_for
from django.core.urlresolvers import reverse
from maasserver import eventloop
from maasserver.rpc import regionservice
from maasserver.testing.eventloop import RegionEventLoopFixture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASTransactionServerTestCase
from netaddr import IPAddress
from provisioningserver.utils.network import get_all_interface_addresses
from provisioningserver.utils.testing import MAASIDFixture
from testtools.matchers import (
    Equals,
    GreaterThan,
    IsInstance,
    KeysEqual,
    LessThan,
    MatchesAll,
    MatchesDict,
    MatchesListwise,
    MatchesSetwise,
)
from twisted.internet.defer import (
    CancelledError,
    fail,
    inlineCallbacks,
)


is_valid_port = MatchesAll(
    IsInstance(int), GreaterThan(0), LessThan(2 ** 16))


class RPCViewTest(MAASTransactionServerTestCase):

    def setUp(self):
        super(RPCViewTest, self).setUp()
        self.maas_id = None

        def set_maas_id(maas_id):
            self.maas_id = maas_id

        self.set_maas_id = self.patch(regionservice, "set_maas_id")
        self.set_maas_id.side_effect = set_maas_id

        def get_maas_id():
            return self.maas_id

        self.get_maas_id = self.patch(regionservice, "get_maas_id")
        self.get_maas_id.side_effect = get_maas_id

    def test_rpc_info_when_rpc_advertise_not_present(self):
        getServiceNamed = self.patch_autospec(
            eventloop.services, "getServiceNamed")
        getServiceNamed.side_effect = KeyError

        response = self.client.get(reverse('rpc-info'))
        self.assertEqual("application/json", response["Content-Type"])
        info = json.loads(response.content.decode("unicode_escape"))
        self.assertEqual({"eventloops": None}, info)

    def test_rpc_info_when_rpc_advertise_not_running(self):
        response = self.client.get(reverse('rpc-info'))
        self.assertEqual("application/json", response["Content-Type"])
        info = json.loads(response.content.decode("unicode_escape"))
        self.assertEqual({"eventloops": None}, info)

    def simulateExceptionInAdvertiseService(self, exception):
        # Simulate a time-out when getting the advertising instance.
        eventloop.loop.populate().wait(2.0)
        advertiser = eventloop.services.getServiceNamed("rpc-advertise")
        self.patch(advertiser, "_tryPromote")
        advertiser._tryPromote.return_value = fail(exception)

    def test_rpc_info_when_rpc_advertise_not_fully_started(self):
        self.useFixture(RegionEventLoopFixture("rpc", "rpc-advertise"))

        # Simulate a time-out when getting the advertising instance.
        self.simulateExceptionInAdvertiseService(CancelledError())

        eventloop.start().wait(2.0)
        self.addCleanup(lambda: eventloop.reset().wait(5))

        response = self.client.get(reverse('rpc-info'))
        self.assertEqual("application/json", response["Content-Type"])
        info = json.loads(response.content.decode("unicode_escape"))
        self.assertEqual({"eventloops": None}, info)

    def test_rpc_info_when_rpc_advertise_startup_failed(self):
        self.useFixture(RegionEventLoopFixture("rpc", "rpc-advertise"))

        # Simulate a crash when the rpc-advertise service starts.
        self.simulateExceptionInAdvertiseService(factory.make_exception())

        eventloop.start().wait(2.0)
        self.addCleanup(lambda: eventloop.reset().wait(5))

        response = self.client.get(reverse('rpc-info'))
        self.assertEqual("application/json", response["Content-Type"])
        info = json.loads(response.content.decode("unicode_escape"))
        self.assertEqual({"eventloops": None}, info)

    def test_rpc_info_when_rpc_advertise_running(self):
        region = factory.make_RegionController()
        self.useFixture(MAASIDFixture(region.system_id))
        region.owner = factory.make_admin()
        region.save()
        self.useFixture(RegionEventLoopFixture("rpc", "rpc-advertise"))

        eventloop.start().wait(5)
        self.addCleanup(lambda: eventloop.reset().wait(5))

        getServiceNamed = eventloop.services.getServiceNamed

        @wait_for(5)
        @inlineCallbacks
        def wait_for_startup():
            # Wait for the rpc and the rpc-advertise services to start.
            yield getServiceNamed("rpc").starting
            yield getServiceNamed("rpc-advertise").starting
            # Force an update, because it's very hard to track when the
            # first iteration of the rpc-advertise service has completed.
            yield getServiceNamed("rpc-advertise")._tryUpdate()
        wait_for_startup()

        response = self.client.get(reverse('rpc-info'))

        self.assertEqual("application/json", response["Content-Type"])
        info = json.loads(response.content.decode("unicode_escape"))
        self.assertThat(info, KeysEqual("eventloops"))
        self.assertThat(info["eventloops"], MatchesDict({
            # Each entry in the endpoints dict is a mapping from an
            # event loop to a list of (host, port) tuples. Each tuple is
            # a potential endpoint for connecting into that event loop.
            eventloop.loop.name: MatchesSetwise(*(
                MatchesListwise((Equals(addr), is_valid_port))
                for addr in get_all_interface_addresses()
                if not IPAddress(addr).is_link_local() and
                not IPAddress(addr).is_loopback()
            )),
        }))
