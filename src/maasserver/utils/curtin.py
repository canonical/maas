# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Curtin-related utility functions."""

import curtin


def curtin_supports_feature(feature):
    curtin_features = getattr(curtin, 'FEATURES', [])
    return feature in curtin_features


def curtin_supports_webhook_events():
    """Return True if the installed curtin supports reporting events."""
    return curtin_supports_feature('REPORTING_EVENTS_WEBHOOK')


def curtin_supports_custom_storage():
    """Return True if the installed curtin supports custom storage."""
    return curtin_supports_feature('STORAGE_CONFIG_V1')


def curtin_supports_custom_storage_for_dd():
    """Return True if the installed curtin supports custom storage
       for DD images."""
    return curtin_supports_feature('STORAGE_CONFIG_V1_DD')
