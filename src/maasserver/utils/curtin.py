# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Curtin-related utility functions."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type

import curtin


def curtin_supports_webhook_events():
    curtin_features = getattr(curtin, 'FEATURES', [])
    return 'REPORTING_EVENTS_WEBHOOK' in curtin_features
