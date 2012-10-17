# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Celery demo settings for the maas project: common settings."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

__metaclass__ = type

import os


DEV_ROOT_DIRECTORY = os.path.join(
    os.path.dirname(__file__), os.pardir)


DNS_CONFIG_DIR = os.path.join(
    DEV_ROOT_DIRECTORY, 'run/named/')


DNS_RNDC_PORT = 9154


# Do not include the default RNDC controls statement to avoid
# a conflict while trying to listen on port 943.
DNS_DEFAULT_CONTROLS = False


DHCP_CONFIG_FILE = os.path.join(
    DEV_ROOT_DIRECTORY, 'run/dhcpd.conf')


DHCP_LEASES_FILE = os.path.join(
    DEV_ROOT_DIRECTORY, 'run/dhcpd.leases')
