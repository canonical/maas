# Copyright 2015-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Cisco UCS Power Driver."""


from provisioningserver.drivers import (
    IP_EXTRACTOR_PATTERNS,
    make_ip_extractor,
    make_setting_field,
    SETTING_SCOPE,
)
from provisioningserver.drivers.hardware.ucsm import (
    power_control_ucsm,
    power_state_ucsm,
)
from provisioningserver.drivers.power import PowerDriver


def extract_ucsm_parameters(context):
    url = context.get("power_address")
    username = context.get("power_user")
    password = context.get("power_pass")
    uuid = context.get("uuid")
    return url, username, password, uuid


class UCSMPowerDriver(PowerDriver):
    name = "ucsm"
    chassis = True
    can_probe = True
    can_set_boot_order = False
    description = "Cisco UCS Manager"
    settings = [
        make_setting_field(
            "uuid", "Server UUID", scope=SETTING_SCOPE.NODE, required=True
        ),
        make_setting_field("power_address", "URL for XML API", required=True),
        make_setting_field("power_user", "API user"),
        make_setting_field(
            "power_pass", "API password", field_type="password", secret=True
        ),
    ]
    ip_extractor = make_ip_extractor(
        "power_address", IP_EXTRACTOR_PATTERNS.URL
    )

    def detect_missing_packages(self):
        # uses urllib2 http client - nothing to look for!
        return []

    def power_on(self, system_id, context):
        """Power on UCSM node."""
        url, username, password, uuid = extract_ucsm_parameters(context)
        power_control_ucsm(url, username, password, uuid, maas_power_mode="on")

    def power_off(self, system_id, context):
        """Power off UCSM node."""
        url, username, password, uuid = extract_ucsm_parameters(context)
        power_control_ucsm(
            url, username, password, uuid, maas_power_mode="off"
        )

    def power_query(self, system_id, context):
        """Power query UCSM node."""
        url, username, password, uuid = extract_ucsm_parameters(context)
        return power_state_ucsm(url, username, password, uuid)
