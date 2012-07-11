# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Celery demo settings for the maas project."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

__metaclass__ = type

import os

import celeryconfig
from maas import import_settings

# Extend base settings.
import_settings(celeryconfig)


DEV_ROOT_DIRECTORY = os.path.join(
    os.path.dirname(__file__), os.pardir)


DNS_CONFIG_DIR = os.path.join(
    DEV_ROOT_DIRECTORY, 'run/named/')
