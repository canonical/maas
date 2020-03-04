# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""LXD Power Driver."""

__all__ = []

from urllib.parse import urlparse

from pylxd import Client
from pylxd.exceptions import ClientConnectionFailed, NotFound

from provisioningserver.drivers import (
    IP_EXTRACTOR_PATTERNS,
    make_ip_extractor,
    make_setting_field,
    SETTING_SCOPE,
)
from provisioningserver.drivers.power import PowerDriver
from provisioningserver.maas_certificates import (
    MAAS_CERTIFICATE,
    MAAS_PRIVATE_KEY,
)
from provisioningserver.utils import typed

# LXD Status Codes
LXD_VM_POWER_STATE = {101: "on", 102: "off", 103: "on", 110: "off"}


class LXDError(Exception):
    """Failure communicating to LXD. """


class LXDPowerDriver(PowerDriver):

    name = "lxd"
    chassis = True
    description = "LXD (virtual systems)"
    settings = [
        make_setting_field("power_address", "LXD address", required=True),
        make_setting_field(
            "instance_name",
            "Instance name",
            scope=SETTING_SCOPE.NODE,
            required=True,
        ),
        make_setting_field(
            "password",
            "LXD password (optional)",
            required=False,
            field_type="password",
        ),
    ]
    ip_extractor = make_ip_extractor(
        "power_address", IP_EXTRACTOR_PATTERNS.URL
    )

    def detect_missing_packages(self):
        # python3-pylxd is a MAAS dependency so
        # nothing to check.
        return []

    @typed
    def get_url(self, context: dict):
        """Return url for the LXD host."""
        power_address = context.get("power_address")
        url = urlparse(power_address)
        if not url.scheme:
            # When the scheme is not included in the power address
            # urlparse puts the url into path.
            url = url._replace(scheme="https", netloc="%s" % url.path, path="")
        if not url.port:
            if url.netloc:
                url = url._replace(netloc="%s:8443" % url.netloc)
            else:
                # Similar to above, we need to swap netloc and path.
                url = url._replace(netloc="%s:8443" % url.path, path="")

        return url.geturl()

    @typed
    def get_client(self, system_id: str, context: dict):
        """Connect and return PyLXD client."""
        endpoint = self.get_url(context)
        password = context.get("password")
        try:
            client = Client(
                endpoint=endpoint,
                cert=(MAAS_CERTIFICATE, MAAS_PRIVATE_KEY),
                verify=False,
            )
            if not client.has_api_extensions("virtual-machines"):
                raise LXDError(
                    "Please upgrade your LXD host to 3.19+ for virtual machine support."
                )
            if not client.trusted:
                if password:
                    client.authenticate(password)
                else:
                    raise LXDError(
                        f"{system_id}: Certificate is not trusted and no password was given."
                    )
            return client
        except ClientConnectionFailed:
            raise LXDError(
                f"{system_id}: Failed to connect to the LXD REST API."
            )

    @typed
    def get_machine(self, system_id: str, context: dict):
        """Retrieve LXD VM."""
        client = self.get_client(system_id, context)
        instance_name = context.get("instance_name")
        try:
            machine = client.virtual_machines.get(instance_name)
        except NotFound:
            raise LXDError(f"{system_id}: LXD VM {instance_name} not found.")
        return machine

    @typed
    def power_on(self, system_id: str, context: dict):
        """Power on LXD VM."""
        machine = self.get_machine(system_id, context)
        if LXD_VM_POWER_STATE[machine.status_code] == "off":
            machine.start()

    @typed
    def power_off(self, system_id: str, context: dict):
        """Power off LXD VM."""
        machine = self.get_machine(system_id, context)
        if LXD_VM_POWER_STATE[machine.status_code] == "on":
            machine.stop()

    @typed
    def power_query(self, system_id: str, context: dict):
        """Power query LXD VM."""
        machine = self.get_machine(system_id, context)
        state = machine.status_code
        try:
            return LXD_VM_POWER_STATE[state]
        except KeyError:
            raise LXDError(f"{system_id}: Unknown power status code: {state}")
