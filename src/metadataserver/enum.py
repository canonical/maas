# Copyright 2012-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Enumerations meaningful to the metadataserver application."""

__all__ = [
    "HARDWARE_SYNC_ACTIONS",
    "HARDWARE_TYPE",
    "HARDWARE_TYPE_CHOICES",
    "RESULT_TYPE",
    "RESULT_TYPE_CHOICES",
    "SCRIPT_PARALLEL",
    "SCRIPT_PARALLEL_CHOICES",
    "SCRIPT_STATUS",
    "SCRIPT_STATUS_CHOICES",
    "SCRIPT_STATUS_FAILED",
    "SCRIPT_STATUS_RUNNING",
    "SCRIPT_STATUS_RUNNING_OR_PENDING",
    "SIGNAL_STATUS",
    "SIGNAL_STATUS_CHOICES",
]


from maascommon.enums.node import HardwareDeviceTypeEnum
from maascommon.enums.scriptresult import ScriptStatus
from provisioningserver.enum import enum_choices


class SIGNAL_STATUS:
    OK = "OK"
    FAILED = "FAILED"
    WORKING = "WORKING"
    COMMISSIONING = "COMMISSIONING"
    TESTING = "TESTING"
    TIMEDOUT = "TIMEDOUT"
    INSTALLING = "INSTALLING"
    APPLYING_NETCONF = "APPLYING_NETCONF"
    RELEASING = "RELEASING"


SIGNAL_STATUS_CHOICES = enum_choices(SIGNAL_STATUS)


class SCRIPT_TYPE:
    COMMISSIONING = 0
    # 1 is skipped to keep numbering the same as RESULT_TYPE
    TESTING = 2
    RELEASE = 3


SCRIPT_TYPE_CHOICES = (
    (SCRIPT_TYPE.COMMISSIONING, "Commissioning script"),
    (SCRIPT_TYPE.TESTING, "Testing script"),
    (SCRIPT_TYPE.RELEASE, "Release script"),
)


class RESULT_TYPE:
    COMMISSIONING = 0
    INSTALLATION = 1
    TESTING = 2
    RELEASE = 3


RESULT_TYPE_CHOICES = (
    (RESULT_TYPE.COMMISSIONING, "Commissioning"),
    (RESULT_TYPE.INSTALLATION, "Installation"),
    (RESULT_TYPE.TESTING, "Testing"),
    (RESULT_TYPE.RELEASE, "Release"),
)


class SCRIPT_STATUS:
    PENDING = ScriptStatus.PENDING.value
    RUNNING = ScriptStatus.RUNNING.value
    PASSED = ScriptStatus.PASSED.value
    FAILED = ScriptStatus.FAILED.value
    TIMEDOUT = ScriptStatus.TIMEDOUT.value
    ABORTED = ScriptStatus.ABORTED.value
    DEGRADED = ScriptStatus.DEGRADED.value
    INSTALLING = ScriptStatus.INSTALLING.value
    FAILED_INSTALLING = ScriptStatus.FAILED_INSTALLING.value
    SKIPPED = ScriptStatus.SKIPPED.value
    APPLYING_NETCONF = ScriptStatus.APPLYING_NETCONF.value
    FAILED_APPLYING_NETCONF = ScriptStatus.FAILED_APPLYING_NETCONF.value


SCRIPT_STATUS_CHOICES = (
    (SCRIPT_STATUS.PENDING, "Pending"),
    (SCRIPT_STATUS.RUNNING, "Running"),
    (SCRIPT_STATUS.PASSED, "Passed"),
    (SCRIPT_STATUS.FAILED, "Failed"),
    (SCRIPT_STATUS.TIMEDOUT, "Timed out"),
    (SCRIPT_STATUS.ABORTED, "Aborted"),
    (SCRIPT_STATUS.DEGRADED, "Degraded"),
    (SCRIPT_STATUS.INSTALLING, "Installing dependencies"),
    (SCRIPT_STATUS.FAILED_INSTALLING, "Failed installing dependencies"),
    (SCRIPT_STATUS.SKIPPED, "Skipped"),
    (SCRIPT_STATUS.APPLYING_NETCONF, "Applying custom network configuration"),
    (
        SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
        "Failed to apply custom network configuration",
    ),
)


# ScriptResult statuses which are considered running.
SCRIPT_STATUS_RUNNING = {
    SCRIPT_STATUS.APPLYING_NETCONF,
    SCRIPT_STATUS.INSTALLING,
    SCRIPT_STATUS.RUNNING,
}

SCRIPT_STATUS_RUNNING_OR_PENDING = SCRIPT_STATUS_RUNNING.union(
    {SCRIPT_STATUS.PENDING}
)


# ScriptResult statuses which are considered failed.
SCRIPT_STATUS_FAILED = {
    SCRIPT_STATUS.FAILED,
    SCRIPT_STATUS.TIMEDOUT,
    SCRIPT_STATUS.FAILED_INSTALLING,
    SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
}


class HARDWARE_TYPE:
    NODE = HardwareDeviceTypeEnum.NODE.value
    CPU = HardwareDeviceTypeEnum.CPU.value
    MEMORY = HardwareDeviceTypeEnum.MEMORY.value
    STORAGE = HardwareDeviceTypeEnum.STORAGE.value
    NETWORK = HardwareDeviceTypeEnum.NETWORK.value
    GPU = HardwareDeviceTypeEnum.GPU.value


# Labels are also used for autotagging scripts.
HARDWARE_TYPE_CHOICES = (
    (HARDWARE_TYPE.NODE, "Node"),
    (HARDWARE_TYPE.CPU, "CPU"),
    (HARDWARE_TYPE.MEMORY, "Memory"),
    (HARDWARE_TYPE.STORAGE, "Storage"),
    (HARDWARE_TYPE.NETWORK, "Network"),
    (HARDWARE_TYPE.GPU, "GPU"),
)


class SCRIPT_PARALLEL:
    DISABLED = 0
    INSTANCE = 1
    ANY = 2


SCRIPT_PARALLEL_CHOICES = (
    (SCRIPT_PARALLEL.DISABLED, "Disabled"),
    (SCRIPT_PARALLEL.INSTANCE, "Run along other instances of this script"),
    (SCRIPT_PARALLEL.ANY, "Run along any other script."),
)


class HARDWARE_SYNC_ACTIONS:
    ADDED = "added"
    REMOVED = "removed"
    UPDATED = "updated"
