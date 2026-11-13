# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing resources for `provisioningserver.rackdservices`."""

from unittest.mock import MagicMock

from maastesting.factory import factory
from maastesting.twisted import always_succeed_with
from provisioningserver import services
from provisioningserver.rpc import region
from provisioningserver.rpc.testing import MockLiveClusterToRegionRPCFixture
from provisioningserver.utils.twisted import pause, retries


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


def configure_lease_service_for_one_shot(testcase, service):
    """Helper for getting notifications out of a LeaseSocketService.

    I'm a coroutine that works alongside an @inlineCallbacks test.

    ```
    coroutine = configure_lease_service_for_one_shot(self, service)

    next(coroutine) # First one initialises
    yield next(coroutine) # This one is for putting the service.done in the callback chain
    notifications = yield from coroutine
    assert notifications is not None
    ```
    """
    service.startService()
    testcase.addCleanup(service.stopService)
    # Stop the looping call to check that the notification gets added
    # to notifications.
    process_done = service.done
    service.processor.stop()
    yield process_done
    service.processor = MagicMock()
    create_notification = yield
    create_notification()
    # Loop until the notifications has a notification.
    for elapsed, remaining, wait in retries(5, 0.1, service.reactor):
        if len(service.notifications) > 0:
            return service.notifications
        else:
            yield pause(wait, service.reactor)
    assert False, "No notifications found"
