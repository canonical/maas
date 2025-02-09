# Copyright 2015-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""IPMI Power Driver."""

import enum
import re
from tempfile import NamedTemporaryFile

from provisioningserver.drivers import (
    make_ip_extractor,
    make_setting_field,
    SETTING_SCOPE,
)
from provisioningserver.drivers.power import (
    is_power_parameter_set,
    PowerAuthError,
    PowerConnError,
    PowerDriver,
    PowerError,
    PowerFatalError,
    PowerSettingError,
)
from provisioningserver.events import EVENT_TYPES, send_node_event
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils import shell
from provisioningserver.utils.network import find_ip_via_arp

IPMI_CONFIG = """\
Section Chassis_Boot_Flags
        Boot_Flags_Persistent                         No
        Boot_Device                                   PXE
EndSection
"""


IPMI_CONFIG_WITH_BOOT_TYPE = """\
Section Chassis_Boot_Flags
        Boot_Flags_Persistent                         No
        BIOS_Boot_Type                                %s
        Boot_Device                                   PXE
EndSection
"""

IPMI_ERRORS = {
    "username invalid": {
        "message": (
            "Incorrect username.  Check BMC configuration and try again."
        ),
        "exception": PowerAuthError,
    },
    "password invalid": {
        "message": (
            "Incorrect password.  Check BMC configuration and try again."
        ),
        "exception": PowerAuthError,
    },
    "password verification timeout": {
        "message": (
            "Authentication timeout.  Check BMC configuration and try again."
        ),
        "exception": PowerAuthError,
    },
    "k_g invalid": {
        "message": (
            "Incorrect K_g key.  Check BMC configuration and try again."
        ),
        "exception": PowerAuthError,
    },
    "privilege level insufficient": {
        "message": (
            "Access denied while performing power action."
            "  Check BMC configuration and try again."
        ),
        "exception": PowerAuthError,
    },
    "privilege level cannot be obtained for this user": {
        "message": (
            "Access denied while performing power action."
            "  Check BMC configuration and try again."
        ),
        "exception": PowerAuthError,
    },
    "authentication type unavailable for attempted privilege level": {
        "message": (
            "Access denied while performing power action."
            "  Check BMC configuration and try again."
        ),
        "exception": PowerSettingError,
    },
    "cipher suite id unavailable": {
        "message": (
            "Access denied while performing power action: cipher suite"
            " unavailable.  Check BMC configuration and try again."
        ),
        "exception": PowerSettingError,
    },
    "ipmi 2.0 unavailable": {
        "message": (
            "IPMI 2.0 was not discovered on the BMC."
            "  Please try to use IPMI 1.5 instead."
        ),
        "exception": PowerSettingError,
    },
    "connection timeout": {
        "message": (
            "Connection timed out while performing power action."
            "  Check BMC configuration and connectivity and try again."
        ),
        "exception": PowerConnError,
    },
    "session timeout": {
        "message": (
            "The IPMI session has timed out. MAAS performed several retries."
            "  Check BMC configuration and connectivity and try again."
        ),
        "exception": PowerConnError,
    },
    "internal IPMI error": {
        "message": (
            "An IPMI error has occurred that FreeIPMI does not know how to"
            " handle.  Please try the power action manually, and file a bug if"
            " appropriate."
        ),
        "exception": PowerFatalError,
    },
    "device not found": {
        "message": (
            "Error locating IPMI device."
            "  Check BMC configuration and try again."
        ),
        "exception": PowerSettingError,
    },
    "driver timeout": {
        "message": (
            "Device communication timeout while performing power action."
            "  MAAS performed several retries.  Check BMC configuration and"
            " connectivity and try again."
        ),
        "exception": PowerConnError,
    },
    "message timeout": {
        "message": (
            "Device communication timeout while performing power action."
            "  MAAS performed several retries.  Check BMC configuration and"
            " connectivity and try again."
        ),
        "exception": PowerConnError,
    },
    "BMC busy": {
        "message": (
            "Device busy while performing power action."
            "  MAAS performed several retries.  Please wait and try again."
        ),
        "exception": PowerConnError,
    },
    "could not find inband device": {
        "message": (
            "An inband device could not be found."
            "  Check BMC configuration and try again."
        ),
        "exception": PowerSettingError,
    },
}


maaslog = get_maas_logger("drivers.power.ipmi")


class IPMI_DRIVER:
    DEFAULT = ""
    LAN = "LAN"
    LAN_2_0 = "LAN_2_0"


IPMI_DRIVER_CHOICES = [
    [IPMI_DRIVER.LAN, "LAN [IPMI 1.5]"],
    [IPMI_DRIVER.LAN_2_0, "LAN_2_0 [IPMI 2.0]"],
]


class IPMI_BOOT_TYPE:
    # DEFAULT used to provide backwards compatibility
    DEFAULT = "auto"
    LEGACY = "legacy"
    EFI = "efi"


IPMI_BOOT_TYPE_CHOICES = [
    [IPMI_BOOT_TYPE.DEFAULT, "Automatic"],
    [IPMI_BOOT_TYPE.LEGACY, "Legacy boot"],
    [IPMI_BOOT_TYPE.EFI, "EFI boot"],
]


IPMI_BOOT_TYPE_MAPPING = {
    IPMI_BOOT_TYPE.EFI: "EFI",
    IPMI_BOOT_TYPE.LEGACY: "PC-COMPATIBLE",
}


# Not all IPMI cipher suites are secure. Many disable the authentication,
# integrity, or the confidentiality algorithms. Cipher 0 for example disables
# all encryption leaving everything in plain text. Only ciphers which have
# all three algorithms enabled should be allowed. 30-maas-01-bmc-config will
# pick the most secure IPMI cipher suite id available.
# See http://fish2.com/ipmi/bp.pdf for more information.
IPMI_CIPHER_SUITE_ID_CHOICES = [
    ["17", "17 - HMAC-SHA256::HMAC_SHA256_128::AES-CBC-128"],
    ["3", "3 - HMAC-SHA1::HMAC-SHA1-96::AES-CBC-128"],
    # freeipmi-tools currently defaults to 3. This value is shown to users who
    # upgrade from < 2.9 or when the IPMI cipher suite id isn't discovered.
    ["", "freeipmi-tools default"],
    ["8", "8 - HMAC-MD5::HMAC-MD5-128::AES-CBC-128"],
    ["12", "12 - HMAC-MD5::MD5-128::AES-CBC-128"],
]


IPMI_WORKAROUND_FLAG_CHOICES = [
    ["opensesspriv", "Opensesspriv"],
    ["authcap", "Authcap"],
    ["idzero", "Idzero"],
    ["unexpectedauth", "Unexpectedauth"],
    ["forcepermsg", "Forcepermsg"],
    ["endianseq", "Endianseq"],
    ["intel20", "Intel20"],
    ["supermicro20", "Supermicro20"],
    ["sun20", "Sun20"],
    ["nochecksumcheck", "Nochecksumcheck"],
    ["integritycheckvalue", "Integritycheckvalue"],
    ["ipmiping", "Ipmiping"],
    ["", "None"],
]

IPMI_POWER_OFF_MODE_CHOICES = [
    ["soft", "Soft power off"],
    ["hard", "Power off"],
]


@enum.unique
class IPMI_PRIVILEGE_LEVEL(enum.Enum):
    USER = "USER"
    OPERATOR = "OPERATOR"
    ADMIN = "ADMIN"


IPMI_PRIVILEGE_LEVEL_CHOICES = [
    [IPMI_PRIVILEGE_LEVEL.USER.name, "User"],
    [IPMI_PRIVILEGE_LEVEL.OPERATOR.name, "Operator"],
    [IPMI_PRIVILEGE_LEVEL.ADMIN.name, "Administrator"],
]


class IPMIPowerDriver(PowerDriver):
    name = "ipmi"
    chassis = False
    can_probe = False
    can_set_boot_order = False
    description = "IPMI"
    settings = [
        make_setting_field(
            "power_driver",
            "Power driver",
            field_type="choice",
            choices=IPMI_DRIVER_CHOICES,
            default=IPMI_DRIVER.LAN_2_0,
            required=True,
        ),
        make_setting_field(
            "power_boot_type",
            "Power boot type",
            field_type="choice",
            choices=IPMI_BOOT_TYPE_CHOICES,
            default=IPMI_BOOT_TYPE.DEFAULT,
            required=False,
        ),
        make_setting_field(
            "power_address",
            "IP address",
            field_type="ip_address",
            required=True,
        ),
        make_setting_field("power_user", "Power user"),
        make_setting_field(
            "power_pass", "Power password", field_type="password", secret=True
        ),
        make_setting_field(
            "k_g", "K_g BMC key", field_type="password", secret=True
        ),
        make_setting_field(
            "cipher_suite_id",
            "Cipher Suite ID",
            field_type="choice",
            choices=IPMI_CIPHER_SUITE_ID_CHOICES,
            # freeipmi-tools defaults to 3, not all IPMI BMCs support 17.
            default="3",
        ),
        make_setting_field(
            "privilege_level",
            "Privilege Level",
            field_type="choice",
            choices=IPMI_PRIVILEGE_LEVEL_CHOICES,
            # All MAAS operations can be done as operator.
            default=IPMI_PRIVILEGE_LEVEL.OPERATOR.name,
        ),
        make_setting_field(
            "workaround_flags",
            "Workaround Flags",
            field_type="multiple_choice",
            choices=IPMI_WORKAROUND_FLAG_CHOICES,
            default=["opensesspriv"],
            required=False,
        ),
        make_setting_field(
            "mac_address", "Power MAC", scope=SETTING_SCOPE.NODE
        ),
        make_setting_field(
            "power_off_mode",
            "Power off mode",
            field_type="choice",
            choices=IPMI_POWER_OFF_MODE_CHOICES,
            default="hard",
            required=False,
        ),
    ]
    ip_extractor = make_ip_extractor("power_address")
    wait_time = (4, 8, 16, 32)

    def detect_missing_packages(self):
        if not shell.has_command_available("ipmipower"):
            return ["freeipmi-tools"]
        return []

    def _workarounds(self, workaround_flags):
        if not workaround_flags:
            return []
        return ["-W", ",".join(workaround_flags)]

    @staticmethod
    def _issue_ipmi_chassis_config_command(
        command, power_change, power_address, power_boot_type=None
    ):
        with NamedTemporaryFile("w+", encoding="utf-8") as tmp_config:
            # Write out the chassis configuration.
            if (
                power_boot_type is None
                or power_boot_type == IPMI_BOOT_TYPE.DEFAULT
            ):
                tmp_config.write(IPMI_CONFIG)
            else:
                tmp_config.write(
                    IPMI_CONFIG_WITH_BOOT_TYPE
                    % IPMI_BOOT_TYPE_MAPPING[power_boot_type]
                )
            tmp_config.flush()
            # Use it when running the chassis config command.
            # XXX: Not using call_and_check here because we
            # need to check stderr.
            command = tuple(command) + ("--filename", tmp_config.name)
            result = shell.run_command(*command)
        # XXX newell 2016-11-21 bug=1516065: Some IPMI hardware have timeout
        # issues when trying to set the boot order to PXE.  We want to
        # continue and not raise an error here.
        ipmi_errors = {
            key: IPMI_ERRORS[key]
            for key in IPMI_ERRORS
            if IPMI_ERRORS[key]["exception"] == PowerAuthError
        }
        for error, error_info in ipmi_errors.items():
            if error in result.stderr:
                raise error_info.get("exception")(error_info.get("message"))
        if result.returncode != 0:
            maaslog.warning(
                "Failed to change the boot order to PXE %s: %s"
                % (power_address, result.stderr)
            )

    @staticmethod
    def _issue_ipmipower_command(command, power_change, power_address):
        result = shell.run_command(*command)
        for error, error_info in IPMI_ERRORS.items():
            # ipmipower dumps errors to stdout
            if error in result.stdout:
                raise error_info.get("exception")(error_info.get("message"))
        if result.returncode != 0:
            raise PowerError(
                "Failed to power %s %s: %s"
                % (power_change, power_address, result.stdout)
            )
        match = re.search(r":\s*(on|off)", result.stdout)
        return result.stdout if match is None else match.group(1)

    def _issue_ipmi_command(
        self,
        power_change,
        power_address=None,
        power_user=None,
        power_pass=None,
        power_driver=None,
        power_off_mode=None,
        mac_address=None,
        power_boot_type=None,
        k_g=None,
        cipher_suite_id=None,
        privilege_level=None,
        workaround_flags=None,
        **extra,
    ):
        """Issue command to ipmipower, for the given system."""
        # This script deliberately does not check the current power state
        # before issuing the requested power command. See bug 1171418 for an
        # explanation.

        if workaround_flags is None:
            workaround_flags = ["opensesspriv"]
        if is_power_parameter_set(mac_address) and not is_power_parameter_set(
            power_address
        ):
            power_address = find_ip_via_arp(mac_address)

        # The `-W opensesspriv` workaround is required on many BMCs, and
        # should have no impact on BMCs that don't require it.
        # See https://bugs.launchpad.net/maas/+bug/1287964
        ipmi_chassis_config_command = [
            "ipmi-chassis-config"
        ] + self._workarounds(workaround_flags)
        ipmipower_command = ["ipmipower"] + self._workarounds(workaround_flags)

        # Arguments in common between chassis config and power control. See
        # https://launchpad.net/bugs/1053391 for details of modifying the
        # command for power_driver and power_user.
        common_args = []
        if is_power_parameter_set(power_driver):
            common_args.extend(("--driver-type", power_driver))
        common_args.extend(("-h", power_address))
        if is_power_parameter_set(power_user):
            common_args.extend(("-u", power_user))
        common_args.extend(("-p", power_pass))
        if is_power_parameter_set(k_g):
            common_args.extend(("-k", k_g))
        if is_power_parameter_set(cipher_suite_id):
            if cipher_suite_id != "17":
                maaslog.warning("using a non-secure cipher suite id")
            common_args.extend(("-I", cipher_suite_id))
        if is_power_parameter_set(privilege_level):
            common_args.extend(("-l", privilege_level))
        else:
            # LP:1889788 - Default to communicate at operator level.
            common_args.extend(("-l", IPMI_PRIVILEGE_LEVEL.OPERATOR.name))

        # Update the power commands with common args.
        ipmipower_command.extend(common_args)

        # Additional arguments for the power command.
        if power_change == "on":
            # Update the chassis config commands and call it just when
            # powering on the machine.
            ipmi_chassis_config_command.extend(common_args)
            ipmi_chassis_config_command.append("--commit")
            self._issue_ipmi_chassis_config_command(
                ipmi_chassis_config_command,
                power_change,
                power_address,
                power_boot_type,
            )
            ipmipower_command.append("--cycle")
            ipmipower_command.append("--on-if-off")
        elif power_change == "off":
            if power_off_mode == "soft":
                ipmipower_command.append("--soft")
            else:
                ipmipower_command.append("--off")
        elif power_change == "query":
            ipmipower_command.append("--stat")

        # Update or query the power state.
        return self._issue_ipmipower_command(
            ipmipower_command, power_change, power_address
        )

    def power_on(self, system_id, context):
        try:
            self._issue_ipmi_command("on", **context)
        except PowerAuthError as e:
            if (
                context.get("k_g")
                and str(e) == IPMI_ERRORS["k_g invalid"]["message"]
            ):
                send_node_event(
                    EVENT_TYPES.NODE_POWER_ON_FAILED,
                    system_id,
                    None,
                    "Incorrect K_g key, trying again without K_g key",
                )
                context.pop("k_g")
                self._issue_ipmi_command("on", **context)
            else:
                raise e

    def power_off(self, system_id, context):
        try:
            self._issue_ipmi_command("off", **context)
        except PowerAuthError as e:
            if (
                context.get("k_g")
                and str(e) == IPMI_ERRORS["k_g invalid"]["message"]
            ):
                send_node_event(
                    EVENT_TYPES.NODE_POWER_OFF_FAILED,
                    system_id,
                    None,
                    "Incorrect K_g key, trying again without K_g key",
                )
                context.pop("k_g")
                self._issue_ipmi_command("off", **context)
            else:
                raise e

    def power_query(self, system_id, context):
        try:
            return self._issue_ipmi_command("query", **context)
        except PowerAuthError as e:
            if (
                context.get("k_g")
                and str(e) == IPMI_ERRORS["k_g invalid"]["message"]
            ):
                send_node_event(
                    EVENT_TYPES.NODE_POWER_QUERY_FAILED,
                    system_id,
                    None,
                    "Incorrect K_g key, trying again without K_g key",
                )
                context.pop("k_g")
                return self._issue_ipmi_command("query", **context)
            else:
                raise e

    def power_reset(self, system_id, context):
        raise NotImplementedError()
