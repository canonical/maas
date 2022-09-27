# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the top-level region RPC API."""


from unittest.mock import sentinel

from testtools.deferredruntest import assert_fails_with

from maasserver import eventloop, rpc
from maastesting.crochet import wait_for
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from provisioningserver.rpc import exceptions

wait_for_reactor = wait_for()


class TestFunctions(MAASTestCase):
    @wait_for_reactor
    def test_getClientFor_service_not_running(self):
        return assert_fails_with(
            rpc.getClientFor(sentinel.uuid), exceptions.NoConnectionsAvailable
        )

    @wait_for_reactor
    def test_getClientFor(self):
        getServiceNamed = self.patch(eventloop.services, "getServiceNamed")
        getClientFor = getServiceNamed.return_value.getClientFor
        getClientFor.return_value = sentinel.client
        self.assertIs(getClientFor(sentinel.uuid), sentinel.client)
        self.assertThat(getClientFor, MockCalledOnceWith(sentinel.uuid))

    @wait_for_reactor
    def test_getAllClients_service_not_running(self):
        self.assertEqual([], rpc.getAllClients())

    @wait_for_reactor
    def test_getAllClients(self):
        getServiceNamed = self.patch(eventloop.services, "getServiceNamed")
        getAllClients = getServiceNamed.return_value.getAllClients
        getAllClients.return_value = sentinel.clients
        self.assertIs(getAllClients(), sentinel.clients)
        self.assertThat(getAllClients, MockCalledOnceWith())
