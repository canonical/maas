# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Celery demo settings for the maas project: cluster settings."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

__metaclass__ = type


import os

import celeryconfig_cluster
import democeleryconfig_common
from maas import import_settings

# Silence lint, this will be defined by democeleryconfig_common.
DEV_ROOT_DIRECTORY = None

# Extend base settings.
import_settings(celeryconfig_cluster)

import_settings(democeleryconfig_common)

# Set a fixed CLUSTER_UUID.  In production, this is taken from
# maas_local_celeryconfig.
CLUSTER_UUID = "adfd3977-f251-4f2c-8d61-745dbd690bfc"

MAAS_CELERY_LOG = os.path.join(
    DEV_ROOT_DIRECTORY, 'logs/cluster-worker/current')

