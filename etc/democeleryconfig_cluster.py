# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Celery demo settings for the maas project: cluster settings."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

str = None

__metaclass__ = type


import os

import celeryconfig_cluster
import democeleryconfig_common
from provisioningserver.utils import import_settings

# Silence lint, this will be defined by democeleryconfig_common.
DEV_ROOT_DIRECTORY = None

# Extend base settings.
import_settings(celeryconfig_cluster)

import_settings(democeleryconfig_common)

CELERYD_LOG_FILE = os.path.join(
    DEV_ROOT_DIRECTORY, 'logs/cluster-worker/current')

CELERYBEAT_SCHEDULE_FILENAME = os.path.join(
    DEV_ROOT_DIRECTORY, 'run/celerybeat-cluster-schedule')
