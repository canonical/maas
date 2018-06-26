# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""s390x Power Driver."""

__all__ = []

from provisioningserver.drivers import (
    make_ip_extractor,
    make_setting_field,
    SETTING_SCOPE,
)
from provisioningserver.drivers.hardware.s390x import S390XHMCClient
from provisioningserver.drivers.power import PowerDriver
from provisioningserver.logger import get_maas_logger


maaslog = get_maas_logger('drivers.s390x')


def get_client(context):
    return S390XHMCClient(
        host=context['power_address'], user=context['power_user'],
        password=context['power_pass'])


class S390XPowerDriver(PowerDriver):

    name = 's390x'
    description = "IBM Z (s390x)"
    settings = [
        make_setting_field('power_address', "HMC host", required=True),
        make_setting_field('power_user', "HMC user", required=True),
        make_setting_field(
            'power_pass', "HMC password",
            required=True, field_type='password'),
        make_setting_field(
            'power_uuid', "Partition UUID", scope=SETTING_SCOPE.NODE,
            required=True),
    ]

    ip_extractor = make_ip_extractor('power_address')

    def detect_missing_packages(self):
        return []

    def power_on(self, system_id, context):
        """Power on S390X partition."""
        client = get_client(context)
        client.start_partition(context['power_uuid'])

    def power_off(self, system_id, context):
        """Power off Virsh node."""
        client = get_client(context)
        client.stop_partition(context['power_uuid'])

    def power_query(self, system_id, context):
        """Power query Virsh node."""
        maaslog.info('Getting client')
        client = get_client(context)
        maaslog.info('Querying power state')
        state = client.get_power_state(context['power_uuid'])
        if state in ['starting', 'active', 'stopping', 'degraded']:
            return 'on'
        else:
            return 'off'
