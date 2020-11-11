# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the top-level region RPC API."""


from unittest.mock import sentinel

from crochet import wait_for
from testtools.deferredruntest import assert_fails_with
from testtools.matchers import Equals, Is

from maasserver import eventloop, rpc
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from provisioningserver.rpc import exceptions

wait_for_reactor = wait_for(30)  # 30 seconds.


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
        self.assertThat(getClientFor(sentinel.uuid), Is(sentinel.client))
        self.assertThat(getClientFor, MockCalledOnceWith(sentinel.uuid))

    @wait_for_reactor
    def test_getAllClients_service_not_running(self):
        self.assertThat(rpc.getAllClients(), Equals([]))

    @wait_for_reactor
    def test_getAllClients(self):
        getServiceNamed = self.patch(eventloop.services, "getServiceNamed")
        getAllClients = getServiceNamed.return_value.getAllClients
        getAllClients.return_value = sentinel.clients
        self.assertThat(getAllClients(), Is(sentinel.clients))
        self.assertThat(getAllClients, MockCalledOnceWith())
