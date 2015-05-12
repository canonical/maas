# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Enumerations meaningful to the metadataserver application."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
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


SIGNAL_STATUS_CHOICES = (
    (SIGNAL_STATUS.OK, "OK"),
    (SIGNAL_STATUS.FAILED, "FAILED"),
    (SIGNAL_STATUS.WORKING, "WORKING"),
)


class RESULT_TYPE:

    COMMISSIONING = 0
    INSTALLATION = 1


RESULT_TYPE_CHOICES = (
    (RESULT_TYPE.COMMISSIONING, "Commissioning"),
    (RESULT_TYPE.INSTALLATION, "Installation"),
)
