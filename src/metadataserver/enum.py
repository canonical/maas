# Copyright 2012-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Enumerations meaningful to the metadataserver application."""

__all__ = [
    'SIGNAL_STATUS',
    'SIGNAL_STATUS_CHOICES',
    'RESULT_TYPE',
    'RESULT_TYPE_CHOICES',
    ]


class SIGNAL_STATUS:
    DEFAULT = "OK"

    OK = "OK"
    FAILED = "FAILED"
    WORKING = "WORKING"
    TESTING = "TESTING"


SIGNAL_STATUS_CHOICES = (
    (SIGNAL_STATUS.OK, "OK"),
    (SIGNAL_STATUS.FAILED, "FAILED"),
    (SIGNAL_STATUS.WORKING, "WORKING"),
    (SIGNAL_STATUS.TESTING, "TESTING"),
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


SCRIPT_STATUS_CHOICES = (
    (SCRIPT_STATUS.PENDING, "Pending"),
    (SCRIPT_STATUS.RUNNING, "Running"),
    (SCRIPT_STATUS.PASSED, "Passed"),
    (SCRIPT_STATUS.FAILED, "Failed"),
    (SCRIPT_STATUS.TIMEDOUT, "Timed out"),
    (SCRIPT_STATUS.ABORTED, "Aborted"),
)
