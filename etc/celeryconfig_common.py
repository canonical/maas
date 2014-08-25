# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Celery settings common to the region and the cluster controllers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

str = None

__metaclass__ = type


# Location of MAAS' bind configuration files.
DNS_CONFIG_DIR = '/etc/bind/maas'

# RNDC port to be configured by MAAS to communicate with the BIND
# server.
DNS_RNDC_PORT = 954

# Include the default RNDC controls (default RNDC key on port 953).
DNS_DEFAULT_CONTROLS = True

# DHCP leases file, as maintained by ISC dhcpd.
DHCP_LEASES_FILE = '/var/lib/maas/dhcp/dhcpd.leases'

# ISC dhcpd configuration files.
DHCP_CONFIG_FILE = '/etc/maas/dhcpd.conf'
DHCPv6_CONFIG_FILE = '/etc/maas/dhcpd6.conf'

# List of interfaces that the dhcpd should service (if managed by MAAS).
DHCP_INTERFACES_FILE = '/var/lib/maas/dhcpd-interfaces'
DHCPv6_INTERFACES_FILE = '/var/lib/maas/dhcpd6-interfaces'

# Broker connection information.  This is read by the region controller
# and sent to connecting cluster controllers.
# The cluster controllers currently read this same configuration file,
# but the broker URL they receive from the region controller overrides
# this setting.
BROKER_URL = 'amqp://guest:guest@localhost:5672//'

# Logging.
CELERYD_LOG_FILE = '/var/log/maas/celery.log'
CELERYD_LOG_LEVEL = 'INFO'

# Location for the cluster worker schedule file.
CELERYBEAT_SCHEDULE_FILENAME = '/var/lib/maas/celerybeat-cluster-schedule'

WORKER_QUEUE_DNS = 'celery'
WORKER_QUEUE_REGION = 'celery'

# Each cluster should have its own queue created automatically by Celery.
CELERY_CREATE_MISSING_QUEUES = True

CELERY_IMPORTS = (
    # Tasks.
    "provisioningserver.tasks",

    # This import is needed for its side effect: it initializes the
    # cache that allows workers to share data.
    "provisioningserver.initialize_cache",
    )

CELERY_ACKS_LATE = True

# Do not store the tasks' return values (aka tombstones);
# This improves performance.
CELERY_IGNORE_RESULT = True
