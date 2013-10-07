# Copyright 2012-2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Celery demo settings for the maas project: common settings."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

str = None

__metaclass__ = type

import os


DEV_ROOT_DIRECTORY = os.path.join(
    os.path.dirname(__file__), os.pardir)


DNS_CONFIG_DIR = os.path.join(
    DEV_ROOT_DIRECTORY, 'run/named/')


DNS_RNDC_PORT = 9154


# In configuring RNDC, do not include the default "controls" statement that,
# on a production system, would allow the init scripts to control the DNS
# daemon.  It would try to listen on port 953, which causes conflicts.  (The
# similar "controls" statement for the benefit of MAAS itself, on port 954,
# will still be there).
DNS_DEFAULT_CONTROLS = False


DHCP_CONFIG_FILE = os.path.join(
    DEV_ROOT_DIRECTORY, 'run/dhcpd.conf')


DHCP_LEASES_FILE = os.path.join(
    DEV_ROOT_DIRECTORY, 'run/dhcpd.leases')
