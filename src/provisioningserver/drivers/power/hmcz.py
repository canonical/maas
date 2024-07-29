# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""HMC Z Driver.

Support for managing DPM partitions via the IBM Hardware Management Console
for Z. The HMC for IBM Z has a different API than the HMC for IBM Power, thus
two different power drivers. See
https://github.com/zhmcclient/python-zhmcclient/issues/494
"""

import contextlib

from twisted.internet.defer import inlineCallbacks

from provisioningserver.drivers import (
    make_ip_extractor,
    make_setting_field,
    SETTING_SCOPE,
)
from provisioningserver.drivers.power import (
    PowerActionError,
    PowerDriver,
    PowerError,
)
from provisioningserver.logger import get_maas_logger
from provisioningserver.rpc.utils import commission_node, create_node
from provisioningserver.utils.twisted import asynchronous, threadDeferred

try:
    from zhmcclient import Client, NotFound, Session, StatusTimeout
except ImportError:
    no_zhmcclient = True
else:
    no_zhmcclient = False

maaslog = get_maas_logger("drivers.power.hmcz")

VERIFY_SSL_YES = "y"
VERIFY_SSL_NO = "n"

VERIFY_SSL_CHOICES = [[VERIFY_SSL_NO, "No"], [VERIFY_SSL_YES, "Yes"]]


class HMCZPowerDriver(PowerDriver):
    name = "hmcz"
    chassis = True
    can_probe = True
    can_set_boot_order = True
    description = "IBM Hardware Management Console (HMC) for Z"
    settings = [
        make_setting_field(
            "power_address",
            "HMC Address",
            field_type="ip_address",
            required=True,
        ),
        make_setting_field("power_user", "HMC username", required=True),
        make_setting_field(
            "power_pass",
            "HMC password",
            field_type="password",
            required=True,
            secret=True,
        ),
        make_setting_field(
            "power_partition_name",
            "HMC partition name",
            scope=SETTING_SCOPE.NODE,
            required=True,
        ),
        make_setting_field(
            "power_verify_ssl",
            "Verify certificate presented by the HMC during SSL/TLS handshake",
            field_type="choice",
            required=True,
            choices=VERIFY_SSL_CHOICES,
            default=VERIFY_SSL_YES,
        ),
    ]
    ip_extractor = make_ip_extractor("power_address")

    def detect_missing_packages(self):
        if no_zhmcclient:
            return ["python3-zhmcclient"]
        else:
            return []

    def _get_partition(self, context: dict):
        session = Session(
            context["power_address"],
            context["power_user"],
            context["power_pass"],
            verify_cert=context.get("power_verify_ssl", "y") == VERIFY_SSL_YES,
        )
        partition_name = context["power_partition_name"]
        client = Client(session)
        # Each HMC manages one or more CPCs(Central Processor Complex). To find
        # a partition MAAS must iterate over all CPCs.
        for cpc in client.cpcs.list():
            if not cpc.dpm_enabled:
                maaslog.warning(
                    f"DPM is not enabled on '{cpc.get_property('name')}', "
                    "skipping"
                )
                continue
            with contextlib.suppress(NotFound):
                return cpc.partitions.find(name=partition_name)
        raise PowerActionError(f"Unable to find '{partition_name}' on HMC!")

    # IBM Z partitions can take awhile to start/stop. Don't wait for completion
    # so power actions don't consume a thread.

    @asynchronous
    @threadDeferred
    def power_on(self, system_id: str, context: dict):
        """Power on IBM Z DPM."""
        partition = self._get_partition(context)
        status = partition.get_property("status")
        if status in {"paused", "terminated"}:
            # A "paused" or "terminated" partition can only be started if
            # it is stopped first. MAAS can't execute the start action until
            # the stop action completes. This holds the thread in MAAS for ~30s.
            # IBM is aware this isn't optimal for us so they are looking into
            # modifying IBM Z to go into a stopped state.
            partition.stop(wait_for_completion=True)
        elif status == "stopping":
            # The HMC does not allow a machine to be powered on if its
            # currently stopping. Wait 120s for it which should be more
            # than enough time.
            try:
                partition.wait_for_status("stopped", 120)
            except StatusTimeout:
                # If 120s isn't enough time raise a PowerError() which will
                # trigger the builtin retry code in the base PowerDriver()
                # class.
                raise PowerError(
                    "Partition is stuck in a "
                    f"{partition.get_property('status')} state!"
                )

        partition.start(wait_for_completion=False)

    @asynchronous
    @threadDeferred
    def power_off(self, system_id: str, context: dict):
        """Power off IBM Z DPM."""
        partition = self._get_partition(context)
        status = partition.get_property("status")
        if status == "starting":
            # The HMC does not allow a machine to be powered off if its
            # currently starting. Wait 120s for it which should be more
            # than enough time.
            try:
                partition.wait_for_status("active", 120)
            except StatusTimeout:
                # If 120s isn't enough time raise a PowerError() which will
                # trigger the builtin retry code in the base PowerDriver()
                # class.
                raise PowerError(
                    "Partition is stuck in a "
                    f"{partition.get_property('status')} state!"
                )
        partition.stop(wait_for_completion=False)

    @asynchronous
    @threadDeferred
    def power_query(self, system_id: str, context: dict):
        """Power on IBM Z DPM."""
        partition = self._get_partition(context)
        status = partition.get_property("status")
        # IBM Z takes time to start or stop a partition. It returns a
        # transitional state during this time. Associate the transitional
        # state with on or off so MAAS doesn't repeatedly issue a power
        # on or off command.
        if status in {"starting", "active", "degraded"}:
            return "on"
        elif status in {"stopping", "stopped", "paused", "terminated"}:
            # A "paused" state isn't on or off, it just means the partition
            # isn't currently executing instructions. A partition can go into
            # a "paused" state if `shutdown -h now` is executed in the
            # partition. "paused" also happens when transitioning between
            # "starting" and "active". Consider it off so MAAS can start
            # it again when needed. IBM is aware this is weird and is working
            # on a solution.
            return "off"
        else:
            return "unknown"

    @asynchronous
    @threadDeferred
    def set_boot_order(self, system_id: str, context: dict, order: list):
        """Set the specified boot order.

        :param system_id: `Node.system_id`
        :param context: Power settings for the node.
        :param order: An ordered list of network or storage devices.
        """
        partition = self._get_partition(context)
        status = partition.get_property("status")

        if status in {"starting", "stopping"}:
            # The HMC does not allow a machine's boot order to be reconfigured
            # while in a transitional state. Wait for it to complete. If this
            # times out allow it to be raised so the region can log it.
            partition.wait_for_status(["stopped", "active"], 120)

        # You can only specify one boot device on IBM Z
        boot_device = order[0]
        if boot_device.get("mac_address"):
            nic = partition.nics.find(
                **{"mac-address": boot_device["mac_address"]}
            )
            partition.update_properties(
                {
                    "boot-device": "network-adapter",
                    "boot-network-device": nic.uri,
                }
            )
        else:
            for storage_group in partition.list_attached_storage_groups():
                # MAAS/LXD detects the storage volume UUID or serial-number as its serial.
                storage_volumes = storage_group.storage_volumes.list(
                    full_properties=True
                )
                for vol in storage_volumes:
                    if boot_device["serial"].upper() in [
                        vol.properties.get("uuid", "").strip(),
                        vol.properties.get("serial-number", "").strip(),
                    ]:
                        partition.update_properties(
                            {
                                "boot-device": "storage-volume",
                                "boot-storage-volume": vol.uri,
                            }
                        )
                        return

            raise PowerError(
                f'No storage volume found with {boot_device["serial"].upper()}'
            )


@asynchronous
@inlineCallbacks
def probe_hmcz_and_enlist(
    user: str,
    hostname: str,
    username: str,
    password: str,
    accept_all: bool = False,
    domain: str = None,
    prefix_filter: str = None,
    verify_ssl: bool = True,
):
    """Extracts all of the VMs from an HMC for Z and enlists them into MAAS.

    :param user: user for the nodes.
    :param hostname: Hostname for Proxmox
    :param username: The username to connect to Proxmox to
    :param password: The password to connect to Proxmox with.
    :param accept_all: If True, commission enlisted nodes.
    :param domain: What domain discovered machines to be apart of.
    :param prefix_filter: only enlist nodes that have the prefix.
    :param verify_ssl: Whether SSL connections should be verified.
    """
    session = Session(hostname, username, password, verify_cert=verify_ssl)
    client = Client(session)
    # Each HMC manages one or more CPCs(Central Processor Complex). Iterate
    # over all CPCs to find all partitions to add.
    for cpc in client.cpcs.list():
        if not cpc.dpm_enabled:
            maaslog.warning(
                f"DPM is not enabled on '{cpc.get_property('name')}', "
                "skipping"
            )
            continue
        for partition in cpc.partitions.list():
            if prefix_filter and not partition.name.startswith(prefix_filter):
                continue

            system_id = yield create_node(
                [
                    nic.get_property("mac-address")
                    for nic in partition.nics.list()
                ],
                "s390x",
                "hmcz",
                {
                    "power_address": hostname,
                    "power_user": username,
                    "power_pass": password,
                    "power_partition_name": partition.name,
                    "power_verify_ssl": (
                        VERIFY_SSL_NO
                        if verify_ssl is False
                        else VERIFY_SSL_YES
                    ),
                },
                domain,
                partition.name,
            )

            # If the system_id is None an error occured when creating the machine.
            # Most likely the error is the node already exists.
            if system_id is None:
                continue

            if accept_all:
                yield commission_node(system_id, user)
