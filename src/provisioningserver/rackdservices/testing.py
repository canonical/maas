# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing resources for `provisioningserver.rackdservices`."""

from maastesting.factory import factory
from maastesting.twisted import always_succeed_with
from provisioningserver import services
from provisioningserver.rpc import region
from provisioningserver.rpc.testing import MockLiveClusterToRegionRPCFixture


def prepareRegionForGetControllerType(test, is_region=False, is_rack=True):
    """Set up a mock region controller that responds to `GetControllerType`.

    In addition it sets the MAAS ID to a new random value. It arranges for
    tear-down at the end of the test.

    :return: The running RPC service, and the protocol instance.
    """
    fixture = test.useFixture(MockLiveClusterToRegionRPCFixture())
    protocol, connecting = fixture.makeEventLoop(region.GetControllerType)
    protocol.RegisterRackController.side_effect = always_succeed_with(
        {"system_id": factory.make_name("maas-id")}
    )
    protocol.GetControllerType.side_effect = always_succeed_with(
        {"is_region": is_region, "is_rack": is_rack}
    )

    def connected(teardown):
        test.addCleanup(teardown)
        return services.getServiceNamed("rpc"), protocol

    return connecting.addCallback(connected)
