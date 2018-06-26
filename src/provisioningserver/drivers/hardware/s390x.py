# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from zhmcclient import (
    Client,
    Session,
)

from provisioningserver.logger import get_maas_logger


maaslog = get_maas_logger('drivers.s390x')


class S390XHMCClient:

    def __init__(self, host, user, password):
        maaslog.info('Creating session')
        self.session = Session(host, user, password)
        maaslog.info('Creating client')
        self.client = Client(self.session)

    def get_power_state(self, uuid):
        maaslog.info('Checking power state for {}'.format(uuid))
        partition = self._get_partition(uuid)
        return partition.properties['status']

    def start_partition(self, uuid):
        partition = self._get_partition(uuid)
        partition.start(wait_for_completion=False)

    def stop_partition(self, uuid):
        partition = self._get_partition(uuid)
        partition.stop(wait_for_completion=False)

    def _get_partition(self, uuid):
        maaslog.info('Finding partition {}'.format(uuid))
        for cpc in self.client.cpcs.list():
            maaslog.info('Found a CPC')
            if not cpc.dpm_enabled:
                maaslog.info('DPM is not enabled')
                continue
            maaslog.info('Listing partitions')
            partitions = cpc.partitions.list(
                full_properties=True, filter_args={'object-id': uuid})
            if partitions:
                maaslog.info('Found partition')
                return partitions[0]
