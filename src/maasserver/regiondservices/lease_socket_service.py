from twisted.internet.defer import inlineCallbacks

from maasserver.rpc import leases
from maasserver.utils.threads import deferToDatabase
from provisioningserver.rackdservices.lease_socket_service import (
    LeaseSocketService,
)
from provisioningserver.utils.env import get_maas_id


class RegionLeaseSocketService(LeaseSocketService):
    def __init__(self, reactor):
        super(RegionLeaseSocketService, self).__init__(None, reactor)

    @inlineCallbacks
    def processNotification(self, notification, clock=None):
        notification["cluster_uuid"] = get_maas_id()
        yield deferToDatabase(
            leases.update_lease,
            **notification,
        )
