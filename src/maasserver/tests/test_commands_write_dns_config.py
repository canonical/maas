# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the write_dns_config command."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


import os

from django.conf import settings
from django.core.management import call_command
from maasserver.enum import (
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from netaddr import IPNetwork
from provisioningserver import tasks
from provisioningserver.dns.testing import patch_dns_config_path
from testtools.matchers import FileExists


class TestWriteDNSConfigCommand(MAASServerTestCase):

    def test_write_dns_config_writes_zone_file(self):
        dns_conf_dir = self.make_dir()
        patch_dns_config_path(self, dns_conf_dir)
        self.patch(settings, 'DNS_CONNECT', True)
        # Prevent rndc task dispatch.
        self.patch(tasks, "rndc_command")
        domain = factory.make_string()
        factory.make_NodeGroup(
            name=domain,
            network=IPNetwork('192.168.0.1/24'),
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        call_command('write_dns_config')
        zone_file = os.path.join(dns_conf_dir, 'zone.%s' % domain)
        self.assertThat(zone_file, FileExists())
