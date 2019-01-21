# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Nova Power Driver."""

__all__ = []

from importlib import (
    import_module,
    invalidate_caches,
)
import urllib

from provisioningserver.drivers import (
    IP_EXTRACTOR_PATTERNS,
    make_ip_extractor,
    make_setting_field,
    SETTING_SCOPE,
)
from provisioningserver.drivers.power import (
    PowerAuthError,
    PowerDriver,
    PowerError,
    PowerFatalError,
    PowerToolError,
)
from provisioningserver.logger import get_maas_logger


maaslog = get_maas_logger("drivers.power.nova")


class NovaPowerState:
    NOSTATE = 0
    RUNNING = 1
    PAUSED = 3
    SHUTDOWN = 4
    CRASHED = 6
    SUSPENDED = 7


class NovaPowerDriver(PowerDriver):

    name = 'nova'
    chassis = True
    description = "OpenStack Nova"
    settings = [
        make_setting_field(
            'nova_id', "Host UUID", required=True,
            scope=SETTING_SCOPE.NODE),
        make_setting_field('os_tenantname', "Tenant name", required=True),
        make_setting_field('os_username', "Username", required=True),
        make_setting_field(
            'os_password', "Password", field_type='password',
            required=True),
        make_setting_field('os_authurl', "Auth URL", required=True),
        # Since OpenStack Queens Keystone supports ONLY v3 auth
        # hence parameters below are required to work with that version
        # but old one are left as an option for backward compatibility
        # with prev OpenStack versions
        make_setting_field('user_domain_name', "User Domain name"),
        make_setting_field('project_domain_name', "Project Domain name"),
    ]
    ip_extractor = make_ip_extractor('os_authurl', IP_EXTRACTOR_PATTERNS.URL)

    nova_api = None

    def power_control_nova(
            self, power_change, nova_id=None, os_tenantname=None,
            os_username=None, os_password=None, os_authurl=None,
            **extra):
        """Control power of nova instances."""
        if not self.try_novaapi_import():
            raise PowerToolError("Missing the python3-novaclient package.")
        if user_domain_name != "" and project_domain_name != "":
            nova = self.nova_api.Client(2, username=os_username,
                                        password=os_password,
                                        project_name=os_tenantname,
                                        auth_url=os_authurl,
                                        user_domain_name=user_domain_name,
                                        project_domain_name=project_domain_name)
        else:
            nova = self.nova_api.Client(2, os_username,
                                        os_password,
                                        os_tenantname,
                                        os_authurl)

        try:
            urllib.request.urlopen(os_authurl)
        except urllib.error.URLError:
            raise PowerError('%s: URL error' % os_authurl)
        try:
            nova.authenticate()
        except self.nova_api.exceptions.Unauthorized:
            raise PowerAuthError('Failed to authenticate with OpenStack')
        try:
            pwr_stateStr = "OS-EXT-STS:power_state"
            tsk_stateStr = "OS-EXT-STS:task_state"
            vm_stateStr = "OS-EXT-STS:vm_state"
            power_state = getattr(nova.servers.get(nova_id), pwr_stateStr)
            task_state = getattr(nova.servers.get(nova_id), tsk_stateStr)
            vm_state = getattr(nova.servers.get(nova_id), vm_stateStr)
        except self.nova_api.exceptions.NotFound:
            raise PowerError('%s: Instance id not found' % nova_id)

        if power_state == NovaPowerState.NOSTATE:
            raise PowerFatalError('%s: Failed to get power state' % nova_id)
        if power_state == NovaPowerState.RUNNING:
            if (power_change == 'off' and task_state != 'powering-off' and
               vm_state != 'stopped'):
                nova.servers.get(nova_id).stop()
            elif power_change == 'query':
                return 'on'
        if power_state == NovaPowerState.SHUTDOWN:
            if (power_change == 'on' and task_state != 'powering-on' and
               vm_state != 'active'):
                nova.servers.get(nova_id).start()
            elif power_change == 'query':
                return 'off'

    def try_novaapi_import(self):
        """Attempt to import the novaclient API. This API is provided by the
        python3-novaclient package; if it doesn't work out, we need to notify
        the user so they can install it.
        """
        invalidate_caches()
        try:
            if self.nova_api is None:
                self.nova_api = import_module('novaclient.client')
        except ImportError:
            return False
        else:
            return True

    def detect_missing_packages(self):
        """Detect missing package python3-novaclient."""
        if not self.try_novaapi_import():
            return ["python3-novaclient"]
        return []

    def power_on(self, system_id, context):
        """Power on nova instance."""
        self.power_control_nova('on', **context)

    def power_off(self, system_id, context):
        """Power off nova instance."""
        self.power_control_nova('off', **context)

    def power_query(self, system_id, context):
        """Power query nova instance."""
        return self.power_control_nova('query', **context)
