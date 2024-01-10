# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `osystems` module."""


from twisted.internet.defer import succeed

from maasserver.clusterrpc.osystems import validate_license_key
from maasserver.rpc import getAllClients
from maasserver.rpc.testing.fixtures import RunningClusterRPCFixture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestValidateLicenseKey(MAASServerTestCase):
    """Tests for `validate_license_key`."""

    def test_returns_True_with_one_cluster(self):
        # The Windows driver is known accept a license key in the format of
        # 00000-00000-00000-00000-00000.
        factory.make_RackController()
        key = "00000-00000-00000-00000-00000"
        self.useFixture(RunningClusterRPCFixture())
        is_valid = validate_license_key("windows", "win2012", key)
        self.assertTrue(is_valid)

    def test_returns_True_with_two_cluster(self):
        # The Windows driver is known accept a license key in the format of
        # 00000-00000-00000-00000-00000.
        factory.make_RackController()
        factory.make_RackController()
        key = "00000-00000-00000-00000-00000"
        self.useFixture(RunningClusterRPCFixture())
        is_valid = validate_license_key("windows", "win2012", key)
        self.assertTrue(is_valid)

    def test_returns_True_when_only_one_cluster_returns_True(self):
        # The Windows driver is known accept a license key in the format of
        # 00000-00000-00000-00000-00000.
        factory.make_RackController()
        factory.make_RackController()
        self.useFixture(RunningClusterRPCFixture())

        clients = getAllClients()
        for index, client in enumerate(clients):
            callRemote = self.patch(client._conn, "callRemote")
            if index == 0:
                # The first client returns True.
                callRemote.return_value = succeed({"is_valid": True})
            else:
                # All clients but the first return False.
                callRemote.return_value = succeed({"is_valid": False})

        is_valid = validate_license_key(
            "windows", "win2012", factory.make_name("key")
        )
        self.assertTrue(is_valid)

    def test_returns_True_when_only_one_cluster_returns_True_others_fail(self):
        # The Windows driver is known accept a license key in the format of
        # 00000-00000-00000-00000-00000.
        factory.make_RackController()
        factory.make_RackController()
        self.useFixture(RunningClusterRPCFixture())

        clients = getAllClients()
        for index, client in enumerate(clients):
            callRemote = self.patch(client._conn, "callRemote")
            if index == 0:
                # The first client returns True.
                callRemote.return_value = succeed({"is_valid": True})
            else:
                # All clients but the first raise an exception.
                callRemote.side_effect = ZeroDivisionError()

        is_valid = validate_license_key(
            "windows", "win2012", factory.make_name("key")
        )
        self.assertTrue(is_valid)

    def test_returns_False_with_one_cluster(self):
        factory.make_RackController()
        key = factory.make_name("invalid-key")
        self.useFixture(RunningClusterRPCFixture())
        is_valid = validate_license_key("windows", "win2012", key)
        self.assertFalse(is_valid)

    def test_returns_False_when_all_clusters_fail(self):
        factory.make_RackController()
        factory.make_RackController()
        self.useFixture(RunningClusterRPCFixture())

        clients = getAllClients()
        for index, client in enumerate(clients):
            # All clients raise an exception.
            callRemote = self.patch(client._conn, "callRemote")
            callRemote.side_effect = ZeroDivisionError()

        is_valid = validate_license_key(
            "windows", "win2012", factory.make_name("key")
        )
        self.assertFalse(is_valid)
