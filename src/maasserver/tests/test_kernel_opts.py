# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test composition of kernel command lines."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import httplib
import os

from django.conf import settings
from maasserver.api import get_boot_purpose
from maasserver.kernel_opts import (
    compose_enlistment_preseed_url,
    compose_kernel_command_line,
    compose_preseed_opt,
    compose_preseed_url,
    get_last_directory,
    ISCSI_TARGET_NAME_PREFIX,
    )
from maasserver.preseed import (
    get_enlist_preseed,
    get_preseed,
    )
from maasserver.server_address import get_maas_facing_server_address
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
from maastesting.matchers import ContainsAll
from provisioningserver.pxe.tftppath import compose_image_path
from testtools.matchers import StartsWith


class TestUtilitiesKernelOpts(TestCase):

    def test_get_last_directory(self):
        root = self.make_dir()
        dir1 = os.path.join(root, '20120405')
        dir2 = os.path.join(root, '20120105')
        dir3 = os.path.join(root, '20120403')
        os.makedirs(dir1)
        os.makedirs(dir2)
        os.makedirs(dir3)
        self.assertEqual(dir1, get_last_directory(root))


class TestKernelOpts(TestCase):

    def test_compose_kernel_command_line_accepts_None_for_unknown_node(self):
        self.assertIn(
            'suite=precise',
            compose_kernel_command_line(
                None, factory.make_name('arch'), factory.make_name('subarch'),
                purpose=factory.make_name('purpose')))

    def test_compose_kernel_command_line_includes_preseed_url(self):
        node = factory.make_node()
        self.assertIn(
            "auto url=%s" % compose_preseed_url(node),
            compose_kernel_command_line(
                node, node.architecture, 'generic',
                purpose=factory.make_name('purpose')))

    def test_compose_kernel_command_line_includes_initrd(self):
        node = factory.make_node()
        initrd_path = compose_image_path(
            node.architecture, 'generic', 'precise',
            purpose=get_boot_purpose(node))
        self.assertIn(
            "initrd=%s" % initrd_path,
            compose_kernel_command_line(
                node, node.architecture, 'generic',
                purpose=get_boot_purpose(node)))

    def test_compose_kernel_command_line_includes_suite(self):
        # At the moment, the OS release we use is hard-coded to "precise."
        node = factory.make_node()
        suite = "precise"
        self.assertIn(
            "suite=%s" % suite,
            compose_kernel_command_line(
                node, node.architecture, 'generic',
                purpose=factory.make_name('purpose')))

    def test_compose_kernel_command_line_includes_hostname_and_domain(self):
        node = factory.make_node()
        # Cobbler seems to hard-code domain to "local.lan"; we may want
        # to change it, and update this test.
        domain = "local.lan"
        self.assertThat(
            compose_kernel_command_line(
                node, node.architecture, 'generic',
                purpose=factory.make_name('purpose')),
            ContainsAll([
                "hostname=%s" % node.hostname,
                "domain=%s" % domain,
                ]))

    def test_compose_kernel_command_line_makes_up_hostname_for_new_node(self):
        dummy_hostname = 'maas-enlist'
        self.assertIn(
            "hostname=%s" % dummy_hostname,
            compose_kernel_command_line(
                None, factory.make_name('arch'),
                factory.make_name('subarch'),
                purpose=factory.make_name('purpose')))

    def test_compose_kernel_command_line_includes_locale(self):
        node = factory.make_node()
        locale = "en_US"
        self.assertIn(
            "locale=%s" % locale,
            compose_kernel_command_line(
                node, node.architecture, 'generic',
                purpose=factory.make_name('purpose')))

    def test_compose_kernel_command_line_includes_log_settings(self):
        node = factory.make_node()
        log_host = factory.getRandomIPAddress()
        self.patch(settings, 'DEFAULT_MAAS_URL', 'http://%s/' % log_host)
        # Port 514 (UDP) is syslog.
        log_port = "514"
        text_priority = "critical"
        self.assertThat(
            compose_kernel_command_line(
                node, node.architecture, 'generic',
                purpose=factory.make_name('purpose')),
            ContainsAll([
                "log_host=%s" % log_host,
                "log_port=%s" % log_port,
                "text priority=%s" % text_priority,
                ]))

    def test_compose_kernel_command_line_inc_purpose_opts(self):
        # The result of compose_kernel_command_line includes the purpose
        # options for a non "commissioning" node.
        self.assertIn(
            "netcfg/choose_interface=auto",
            compose_kernel_command_line(
                None, factory.make_name('arch'),
                factory.make_name('subarch'),
                purpose=factory.make_name('purpose')))

    def create_ephemeral_info(self, name, arch):
        """Create a pseudo-real ephemeral info file."""
        release = 'precise'
        epheneral_info = """
            release=precise
            stream=ephemeral
            label=release
            serial=20120424
            arch=i386
            name=%s
            """ % name
        ephemeral_root = self.make_dir()
        self.patch(settings, 'EPHEMERAL_ROOT', ephemeral_root)
        ephemeral_dir = os.path.join(
            ephemeral_root, release, 'ephemeral', arch,
            factory.make_name('release'))
        os.makedirs(ephemeral_dir)
        factory.make_file(
            ephemeral_dir, name='info', contents=epheneral_info)

    def test_compose_kernel_command_line_inc_purpose_opts_comm_node(self):
        # The result of compose_kernel_command_line includes the purpose
        # options for a "commissioning" node.
        ephemeral_name = factory.make_name("ephemeral")
        arch = factory.make_name('arch')
        self.create_ephemeral_info(ephemeral_name, arch)
        node = factory.make_node()
        self.assertThat(
            compose_kernel_command_line(
                node, arch,
                factory.make_name('subarch'),
                purpose="commissioning"),
            ContainsAll([
                "iscsi_target_name=%s:%s" % (
                    ISCSI_TARGET_NAME_PREFIX, ephemeral_name),
                "iscsi_target_port=3260",
                "iscsi_target_ip=%s" % get_maas_facing_server_address(),
                ]))

    def test_compose_enlistment_preseed_url_links_to_enlistment_preseed(self):
        response = self.client.get(compose_enlistment_preseed_url())
        self.assertEqual(
            (httplib.OK, get_enlist_preseed()),
            (response.status_code, response.content))

    def test_compose_enlistment_preseed_url_returns_absolute_link(self):
        url = 'http://%s' % factory.make_name('host')
        self.patch(settings, 'DEFAULT_MAAS_URL', url)
        self.assertThat(
                compose_enlistment_preseed_url(), StartsWith(url))

    def test_compose_preseed_url_links_to_preseed_for_node(self):
        node = factory.make_node()
        response = self.client.get(compose_preseed_url(node))
        self.assertEqual(
            (httplib.OK, get_preseed(node)),
            (response.status_code, response.content))

    def test_compose_preseed_url_returns_absolute_link(self):
        self.assertThat(
            compose_preseed_url(factory.make_node()),
            StartsWith('http://'))

    def test_compose_preseed_kernel_opt_returns_option_for_known_node(self):
        node = factory.make_node()
        self.assertEqual(
            "auto url=%s" % compose_preseed_url(node),
            compose_preseed_opt(node))

    def test_compose_preseed_kernel_opt_returns_option_for_unknown_node(self):
        self.assertEqual(
            "auto url=%s" % compose_enlistment_preseed_url(),
            compose_preseed_opt(None))
