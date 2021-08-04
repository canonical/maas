import logging

from twisted.internet import reactor

from maasserver.dhcp import configure_local_dhcp
from maasserver.region_controller import RegionControllerService
from provisioningserver.utils.twisted import asynchronous, FOREVER

log = logging.getLogger(__name__)


class ProxiedRegionControllerService(RegionControllerService):
    def __init__(
        self,
        postgresListener,
        clock=reactor,
        retryOnFailure=True,
        rbacRetryOnFailureDelay=10,
    ):
        super(ProxiedRegionControllerService, self).__init__(
            postgresListener, clock, retryOnFailure, rbacRetryOnFailureDelay
        )
        self.needsDHCPUpdate = False

    @asynchronous(timeout=FOREVER)
    def startService(self):
        super(ProxiedRegionControllerService, self).startService(
            register_handlers=False
        )
        self.postgresListener.register("sys_dhcp", self.markDHCPForUpdate)
        self.postgresListener.events.connected.registerHandler(
            self.markAllForUpdate
        )

    @asynchronous(timeout=FOREVER)
    def stopService(self):
        d = super().stopService()
        self.postgresListener.unregister("sys_dhcp", self.markDHCPForUpdate)
        return d

    def markAllForUpdate(self):
        super(ProxiedRegionControllerService, self).markAllForUpdate()
        self.markDHCPForUpdate(None, None)

    def markDHCPForUpdate(self, channel, message):
        self.needsDHCPUpdate = True
        self.startProcessing()

    def process(self):
        defers = []

        def _onFailureRetry(failure, attr):
            """Retry update on failure.

            Doesn't mask the failure, the failure is still raised.
            """
            if self.retryOnFailure:
                setattr(self, attr, True)
            return failure

        if self.needsDHCPUpdate:
            self.needsDHCPUpdate = False
            d = configure_local_dhcp()
            d.addErrback(_onFailureRetry, "needsDHCPUpdate")
            defers.append(d)

        super(ProxiedRegionControllerService, self).process(
            pending_defers=defers
        )
