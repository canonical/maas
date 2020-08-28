# Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Curtin-related utility functions."""

__all__ = [
    "curtin_supports_centos_curthook",
    "curtin_supports_custom_storage",
    "curtin_supports_custom_storage_for_dd",
    "curtin_supports_webhook_events",
]

import curtin


def curtin_supports_feature(feature):
    curtin_features = getattr(curtin, "FEATURES", [])
    return feature in curtin_features


def curtin_supports_webhook_events():
    """Return True if the installed curtin supports reporting events."""
    return curtin_supports_feature("REPORTING_EVENTS_WEBHOOK")


def curtin_supports_custom_storage():
    """Return True if the installed curtin supports custom storage."""
    return curtin_supports_feature("STORAGE_CONFIG_V1")


def curtin_supports_custom_storage_for_dd():
    """Return True if the installed curtin supports custom storage
    for DD images."""
    return curtin_supports_feature("STORAGE_CONFIG_V1_DD")


def curtin_supports_centos_curthook():
    """Return True if the installed curtin supports deploying CentOS/RHEL
    storage."""
    return curtin_supports_feature("CENTOS_CURTHOOK_SUPPORT")
