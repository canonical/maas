# Copyright 2020-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""LXD Power Driver."""

from contextlib import contextmanager, suppress
import os
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

from pylxd import Client
from pylxd.client import get_session_for_url
from pylxd.exceptions import ClientConnectionFailed, LXDAPIException, NotFound
import urllib3

from provisioningserver.certificates import (
    Certificate,
    CertificateError,
    get_maas_cert_tuple,
)
from provisioningserver.drivers import (
    IP_EXTRACTOR_PATTERNS,
    make_ip_extractor,
    make_setting_field,
    SETTING_SCOPE,
)
from provisioningserver.drivers.power import PowerDriver
from provisioningserver.logger import get_maas_logger
from provisioningserver.prometheus.metrics import PROMETHEUS_METRICS
from provisioningserver.utils.twisted import asynchronous, threadDeferred

# silence warnings from pylxd because of unverified certs for HTTPS connection
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


maaslog = get_maas_logger("drivers.power.lxd")

# LXD status codes
LXD_VM_POWER_STATE = {101: "on", 102: "off", 103: "on", 110: "off"}

# A policy used when waiting between retries of power changes.
LXD_WAITING_POLICY = (1, 2, 2, 4, 6, 8, 12, 20, 30)


class LXDPowerDriverError(Exception):
    """Failure communicating to LXD."""


class LXDPowerDriver(PowerDriver):
    name = "lxd"
    # Virtual machines on the same host share a single BMC (the hypervisor),
    # so the driver must be a chassis for BMC deduplication to work.
    chassis = True
    can_probe = True
    can_set_boot_order = False
    description = "LXD (virtual systems)"
    wait_time = LXD_WAITING_POLICY
    settings = [
        make_setting_field("power_address", "LXD address", required=True),
        make_setting_field(
            "instance_name",
            "Instance name",
            scope=SETTING_SCOPE.NODE,
            required=True,
        ),
        make_setting_field(
            "project",
            "LXD project",
            required=True,
            default="default",
        ),
        make_setting_field(
            "password",
            "LXD password (optional)",
            required=False,
            field_type="password",
            secret=True,
        ),
        make_setting_field(
            "certificate",
            "LXD certificate (optional)",
            required=False,
        ),
        make_setting_field(
            "key",
            "LXD private key (optional)",
            required=False,
            field_type="password",
            secret=True,
        ),
    ]
    ip_extractor = make_ip_extractor(
        "power_address", IP_EXTRACTOR_PATTERNS.URL
    )

    _pylxd_client_class = Client

    def detect_missing_packages(self):
        # python3-pylxd is a required package
        # for maas and is installed by default.
        return []

    def get_url(self, context: dict):
        """Return url for the LXD host."""
        power_address = context.get("power_address")
        if "://" not in power_address:
            # must have a scheme to be a valid URL
            power_address = f"https://{power_address}"
        url = urlparse(power_address)
        if not url.port:
            url = url._replace(netloc=f"{url.netloc}:8443")
        return url.geturl()

    @asynchronous
    @threadDeferred
    def power_on(self, system_id: str, context: dict):
        """Power on LXD VM."""
        with self._get_machine(system_id, context) as machine:
            power_state = LXD_VM_POWER_STATE[machine.status_code]
            maaslog.debug(f"power_on: {system_id} is {power_state}")
            if power_state == "off":
                machine.start()

    @asynchronous
    @threadDeferred
    def power_off(self, system_id: str, context: dict):
        """Power off LXD VM."""
        with self._get_machine(system_id, context) as machine:
            power_state = LXD_VM_POWER_STATE[machine.status_code]
            maaslog.debug(f"power_off: {system_id} is {power_state}")
            if power_state == "on":
                machine.stop()

    @asynchronous
    @threadDeferred
    def power_query(self, system_id: str, context: dict):
        """Power query LXD VM."""
        with self._get_machine(system_id, context) as machine:
            state = machine.status_code
            try:
                return LXD_VM_POWER_STATE[state]
            except KeyError:
                raise LXDPowerDriverError(  # noqa: B904
                    f"{system_id}: Unknown power status code: {state}"
                )

    @asynchronous
    @threadDeferred
    def power_reset(self, system_id: str, context: dict):
        """Power reset LXD VM."""
        raise NotImplementedError()

    @PROMETHEUS_METRICS.failure_counter("maas_lxd_fetch_machine_failure")
    @contextmanager
    def _get_machine(self, system_id: str, context: dict, fail: bool = True):
        """Retrieve LXD VM.

        If "fail" is False, return None instead of raising an exception.
        """
        instance_name = context.get("instance_name")
        with self._get_client(system_id, context) as client:
            try:
                yield client.virtual_machines.get(instance_name)
            except NotFound:
                if fail:
                    raise LXDPowerDriverError(  # noqa: B904
                        f"{system_id}: LXD VM {instance_name} not found."
                    )
                yield None

    @contextmanager
    def _get_client(
        self,
        system_id: str,
        context: dict,
        project: Optional[str] = None,
    ):
        """Return a context manager with a PyLXD client."""

        def Error(message):
            return LXDPowerDriverError(f"{system_id}: {message}")

        endpoint = self.get_url(context)
        if not project:
            project = context.get("project", "default")

        password = context.get("password")
        try:
            cert_paths = self._get_cert_paths(context)
        except CertificateError as e:
            raise Error(str(e))  # noqa: B904
        maas_certs = get_maas_cert_tuple()
        if not cert_paths and not maas_certs:
            raise Error("No certificates available")

        def client_with_certs(cert):
            session = get_session_for_url(endpoint, cert=cert, verify=False)
            # Don't inherit proxy environment variables
            session.trust_env = False
            client = self._pylxd_client_class(
                endpoint=endpoint,
                project=project,
                cert=cert,
                verify=False,
                session=session,
            )
            if not client.trusted and password:
                try:
                    client.authenticate(password)
                except LXDAPIException as e:
                    raise Error(f"Password authentication failed: {e}") from e
            return client

        try:
            if cert_paths:
                client = client_with_certs(cert_paths)
                if not client.trusted and maas_certs:
                    with suppress(LXDAPIException):
                        # Try to trust the certificate using the controller
                        # certs. If this fails, ignore the error as the trusted
                        # status for the original client is checked later.
                        client_with_certs(maas_certs).certificates.create(
                            "", Path(cert_paths[0]).read_bytes()
                        )
                        # create a new client since the certs are now trusted
                        client = client_with_certs(cert_paths)
            else:
                client = client_with_certs(maas_certs)

            if not client.trusted:
                raise Error(
                    "Certificate is not trusted and no password was given"
                )
        except ClientConnectionFailed as e:
            raise LXDPowerDriverError(
                f"{system_id}: Failed to connect to the LXD REST API: {e}"
            ) from e
        else:
            yield client
        finally:
            for path in cert_paths:
                os.unlink(path)

    def _get_cert_paths(self, context: dict) -> Optional[Tuple[str, str]]:
        """Return a 2-tuple with paths for temporary files containing cert and key.

        If no certificate or key are provided, an empty tuple is returned.

        If invalid material is passed, an error is raised.
        """
        cert = context.get("certificate")
        key = context.get("key")
        if not cert or not key:
            return ()

        cert = Certificate.from_pem(cert, key)
        return cert.tempfiles()
