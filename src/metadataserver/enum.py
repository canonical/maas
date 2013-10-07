# Copyright 2012 Canonical Ltd.  This software is licensed under the
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
    'COMMISSIONING_STATUS',
    'COMMISSIONING_STATUS_CHOICES',
    ]


class COMMISSIONING_STATUS:
    """The vocabulary of a commissioning script's possible statuses."""
    DEFAULT_STATUS = "OK"

    OK = "OK"
    FAILED = "FAILED"
    WORKING = "WORKING"


COMMISSIONING_STATUS_CHOICES = (
    (COMMISSIONING_STATUS.OK, "OK"),
    (COMMISSIONING_STATUS.FAILED, "FAILED"),
    (COMMISSIONING_STATUS.WORKING, "WORKING"),
)
