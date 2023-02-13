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


class SIGNAL_STATUS:
    DEFAULT = "OK"

    OK = "OK"
    FAILED = "FAILED"
    WORKING = "WORKING"
    COMMISSIONING = "COMMISSIONING"
    TESTING = "TESTING"
    TIMEDOUT = "TIMEDOUT"
    INSTALLING = "INSTALLING"
    APPLYING_NETCONF = "APPLYING_NETCONF"


SIGNAL_STATUS_CHOICES = (
    (SIGNAL_STATUS.OK, "OK"),
    (SIGNAL_STATUS.FAILED, "FAILED"),
    (SIGNAL_STATUS.WORKING, "WORKING"),
    (SIGNAL_STATUS.COMMISSIONING, "COMMISSIONING"),
    (SIGNAL_STATUS.TESTING, "TESTING"),
    (SIGNAL_STATUS.TIMEDOUT, "TIMEDOUT"),
    (SIGNAL_STATUS.INSTALLING, "INSTALLING"),
    (SIGNAL_STATUS.APPLYING_NETCONF, "APPLYING_NETCONF"),
)


class SCRIPT_TYPE:
    COMMISSIONING = 0
    # 1 is skipped to keep numbering the same as RESULT_TYPE
    TESTING = 2


SCRIPT_TYPE_CHOICES = (
    (SCRIPT_TYPE.COMMISSIONING, "Commissioning script"),
    (SCRIPT_TYPE.TESTING, "Testing script"),
)


class RESULT_TYPE:
    COMMISSIONING = 0
    INSTALLATION = 1
    TESTING = 2


RESULT_TYPE_CHOICES = (
    (RESULT_TYPE.COMMISSIONING, "Commissioning"),
    (RESULT_TYPE.INSTALLATION, "Installation"),
    (RESULT_TYPE.TESTING, "Testing"),
)


class SCRIPT_STATUS:
    PENDING = 0
    RUNNING = 1
    PASSED = 2
    FAILED = 3
    TIMEDOUT = 4
    ABORTED = 5
    DEGRADED = 6
    INSTALLING = 7
    FAILED_INSTALLING = 8
    SKIPPED = 9
    APPLYING_NETCONF = 10
    FAILED_APPLYING_NETCONF = 11


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
    NODE = 0
    CPU = 1
    MEMORY = 2
    STORAGE = 3
    NETWORK = 4
    GPU = 5


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
