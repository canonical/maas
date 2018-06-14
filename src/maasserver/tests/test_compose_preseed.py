# Copyright 2012-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.compose_preseed`."""

__all__ = []

import random

from maasserver.compose_preseed import (
    compose_enlistment_preseed,
    compose_preseed,
    get_apt_proxy,
)
from maasserver.enum import (
    NODE_STATUS,
    NODE_STATUS_CHOICES,
    POWER_STATE,
    PRESEED_TYPE,
)
from maasserver.models import PackageRepository
from maasserver.models.config import Config
from maasserver.models.signals import bootsources
from maasserver.rpc.testing.fixtures import RunningClusterRPCFixture
from maasserver.testing.factory import factory
from maasserver.testing.osystems import make_usable_osystem
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils import absolute_reverse
from maastesting.matchers import MockCalledOnceWith
from metadataserver.models import NodeKey
from provisioningserver.drivers.osystem import BOOT_IMAGE_PURPOSE
from provisioningserver.rpc.exceptions import (
    NoConnectionsAvailable,
    NoSuchOperatingSystem,
)
from provisioningserver.testing.os import make_osystem
from testtools.matchers import (
    ContainsDict,
    Equals,
    KeysEqual,
    MatchesDict,
    MatchesListwise,
    StartsWith,
)
import yaml


class TestAptProxy(MAASServerTestCase):

    scenarios = (
        ("ipv6", dict(
            default_region_ip=None,
            rack='2001:db8::1',
            result='http://[2001:db8::1]:8000/',
            enable=True,
            use_peer_proxy=False,
            http_proxy='')),
        ("ipv4", dict(
            default_region_ip=None,
            rack='10.0.1.1',
            result='http://10.0.1.1:8000/',
            enable=True,
            use_peer_proxy=False,
            http_proxy='')),
        ("builtin", dict(
            default_region_ip=None,
            rack='region.example.com',
            result='http://region.example.com:8000/',
            enable=True,
            use_peer_proxy=False,
            http_proxy='')),
        ("external", dict(
            default_region_ip=None,
            rack='region.example.com',
            result='http://proxy.example.com:111/',
            enable=True,
            use_peer_proxy=False,
            http_proxy='http://proxy.example.com:111/')),
        ("peer-proxy", dict(
            default_region_ip=None,
            rack='region.example.com',
            result='http://region.example.com:8000/',
            enable=True,
            use_peer_proxy=True,
            http_proxy='http://proxy.example.com:111/')),
        ("disabled", dict(
            default_region_ip=None,
            rack='example.com',
            result=None,
            enable=False,
            use_peer_proxy=False,
            http_proxy='')),
        # If a default IP address for the region is passed in and the rack's
        # URL is empty, the default IP address that was provided should be
        # preferred.
        ("ipv6_default", dict(
            default_region_ip='2001:db8::2',
            rack='',
            result='http://[2001:db8::2]:8000/',
            enable=True,
            use_peer_proxy=False,
            http_proxy='')),
        ("ipv4_default", dict(
            default_region_ip='10.0.1.2',
            rack='',
            result='http://10.0.1.2:8000/',
            enable=True,
            use_peer_proxy=False,
            http_proxy='')),
        ("builtin_default", dict(
            default_region_ip='region.example.com',
            rack='',
            result='http://region.example.com:8000/',
            enable=True,
            use_peer_proxy=False,
            http_proxy='')),
        ("external_default", dict(
            default_region_ip='10.0.0.1',
            rack='',
            result='http://proxy.example.com:111/',
            enable=True,
            use_peer_proxy=False,
            http_proxy='http://proxy.example.com:111/')),
        ("peer-proxy_default", dict(
            default_region_ip='region2.example.com',
            rack='',
            result='http://region2.example.com:8000/',
            enable=True,
            use_peer_proxy=True,
            http_proxy='http://proxy.example.com:111/')),
        ("disabled_default", dict(
            default_region_ip='10.0.0.1',
            rack='',
            result=None,
            enable=False,
            use_peer_proxy=False,
            http_proxy='')),
    )

    def test__returns_correct_url(self):
        import maasserver.compose_preseed as cp_module

        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()
        # Force the server host to be our test data.
        self.patch(
            cp_module,
            'get_maas_facing_server_host').return_value = (
                self.rack if self.rack else self.default_region_ip)
        # Now setup the configuration and arguments, and see what we get back.
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING)
        Config.objects.set_config("enable_http_proxy", self.enable)
        Config.objects.set_config("http_proxy", self.http_proxy)
        Config.objects.set_config("use_peer_proxy", self.use_peer_proxy)
        actual = get_apt_proxy(
            node.get_boot_rack_controller(),
            default_region_ip=self.default_region_ip)
        self.assertEqual(self.result, actual)


class TestComposePreseed(MAASServerTestCase):

    def assertSystemInfo(self, config):
        self.assertThat(config, ContainsDict({
            'system_info': MatchesDict({
                'package_mirrors': MatchesListwise([
                    MatchesDict({
                        "arches": Equals(["i386", "amd64"]),
                        "search": MatchesDict({
                            "primary": Equals(
                                [PackageRepository.get_main_archive().url]),
                            "security": Equals(
                                [PackageRepository.get_main_archive().url]),
                            }),
                        "failsafe": MatchesDict({
                            "primary": Equals(
                                "http://archive.ubuntu.com/ubuntu"),
                            "security": Equals(
                                "http://security.ubuntu.com/ubuntu"),
                            })
                        }),
                    MatchesDict({
                        "arches": Equals(["default"]),
                        "search": MatchesDict({
                            "primary": Equals(
                                [PackageRepository.get_ports_archive().url]),
                            "security": Equals(
                                [PackageRepository.get_ports_archive().url]),
                            }),
                        "failsafe": MatchesDict({
                            "primary": Equals(
                                "http://ports.ubuntu.com/ubuntu-ports"),
                            "security": Equals(
                                "http://ports.ubuntu.com/ubuntu-ports"),
                            })
                        }),
                    ]),
                }),
            }))

    def assertAptConfig(self, config, apt_proxy):
        self.assertThat(config, ContainsDict({
            'apt': ContainsDict({
                'preserve_sources_list': Equals(False),
                'primary': MatchesListwise([
                    MatchesDict({
                        "arches": Equals(["default"]),
                        "uri": Equals(
                            PackageRepository.get_main_archive().url),
                    }),
                ]),
                'proxy': Equals(apt_proxy),
                'security': MatchesListwise([
                    MatchesDict({
                        "arches": Equals(["default"]),
                        "uri": Equals(
                            PackageRepository.get_main_archive().url),
                    }),
                ]),
            })
        }))

    def test_compose_preseed_for_commissioning_node_skips_apt_proxy(self):
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

        rack_controller = factory.make_RackController()
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING)
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        Config.objects.set_config("enable_http_proxy", False)
        preseed = yaml.safe_load(
            compose_preseed(PRESEED_TYPE.COMMISSIONING, node))
        self.assertNotIn('proxy', preseed['apt'])

    def test_compose_preseed_for_commissioning_node_produces_yaml(self):
        rack_controller = factory.make_RackController()
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING)
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        apt_proxy = get_apt_proxy(node.get_boot_rack_controller())
        preseed = yaml.safe_load(
            compose_preseed(PRESEED_TYPE.COMMISSIONING, node))
        self.assertIn('datasource', preseed)
        self.assertIn('MAAS', preseed['datasource'])
        self.assertThat(
            preseed['datasource']['MAAS'],
            KeysEqual(
                'metadata_url', 'consumer_key', 'token_key', 'token_secret'))
        self.assertThat(
            preseed['reporting']['maas'],
            KeysEqual(
                'consumer_key', 'endpoint', 'token_key', 'token_secret',
                'type'))
        self.assertThat(
            preseed['rsyslog']['remotes'],
            KeysEqual('maas'))
        self.assertSystemInfo(preseed)
        self.assertAptConfig(preseed, apt_proxy)

    def test_compose_preseed_for_commissioning_node_has_header(self):
        rack_controller = factory.make_RackController()
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING)
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        preseed = compose_preseed(PRESEED_TYPE.COMMISSIONING, node)
        self.assertThat(preseed, StartsWith("#cloud-config\n"))

    def test_compose_preseed_for_commissioning_node_manages_etc_hosts(self):
        # Regression test for LP:1670444
        rack_controller = factory.make_RackController()
        node = factory.make_Node(
            interface=True, status=random.choice([
                NODE_STATUS.COMMISSIONING, NODE_STATUS.TESTING,
                NODE_STATUS.RESCUE_MODE]), with_empty_script_sets=True)
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        preseed = yaml.safe_load(
            compose_preseed(PRESEED_TYPE.COMMISSIONING, node))
        self.assertTrue(preseed['manage_etc_hosts'])

    def test_compose_preseed_for_commissioning_includes_metadata_status_url(
            self):
        rack_controller = factory.make_RackController(url='')
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING)
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        region_ip = factory.make_ip_address()
        preseed = yaml.safe_load(
            compose_preseed(
                PRESEED_TYPE.COMMISSIONING, node, default_region_ip=region_ip))
        self.assertEqual(
            absolute_reverse('metadata', default_region_ip=region_ip),
            preseed['datasource']['MAAS']['metadata_url'])
        self.assertEqual(
            absolute_reverse(
                'metadata-status', default_region_ip=region_ip,
                args=[node.system_id]),
            preseed['reporting']['maas']['endpoint'])

    def test_compose_preseed_uses_default_region_ip(self):
        rack_controller = factory.make_RackController(url='')
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING)
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        preseed = yaml.safe_load(
            compose_preseed(
                PRESEED_TYPE.COMMISSIONING, node,
                default_region_ip='10.0.0.1'))
        self.assertEqual(
            absolute_reverse('metadata', default_region_ip='10.0.0.1'),
            preseed['datasource']['MAAS']['metadata_url'])
        self.assertEqual(
            absolute_reverse(
                'metadata-status', default_region_ip='10.0.0.1',
                args=[node.system_id]),
            preseed['reporting']['maas']['endpoint'])

    def test_compose_preseed_for_rescue_mode_does_not_include_poweroff(self):
        rack_controller = factory.make_RackController()
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.ENTERING_RESCUE_MODE)
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        preseed = yaml.safe_load(
            compose_preseed(PRESEED_TYPE.COMMISSIONING, node))
        self.assertNotIn('power_state', preseed)

    def test_compose_preseed_for_enable_ssh_does_not_include_poweroff(self):
        rack_controller = factory.make_RackController()
        for status in {NODE_STATUS.COMMISSIONING, NODE_STATUS.TESTING}:
            node = factory.make_Node(
                interface=True, status=status, enable_ssh=True)
            nic = node.get_boot_interface()
            nic.vlan.dhcp_on = True
            nic.vlan.primary_rack = rack_controller
            nic.vlan.save()
            preseed = yaml.safe_load(
                compose_preseed(PRESEED_TYPE.COMMISSIONING, node))
            self.assertNotIn('power_state', preseed)

    def test_compose_preseed_for_enable_ssh_ignored_unsupported_states(self):
        rack_controller = factory.make_RackController()
        for status, status_name in NODE_STATUS_CHOICES:
            if status in {
                    NODE_STATUS.COMMISSIONING,
                    NODE_STATUS.TESTING,
                    NODE_STATUS.ENTERING_RESCUE_MODE}:
                continue
            node = factory.make_Node(
                interface=True, status=status, enable_ssh=True)
            nic = node.get_boot_interface()
            nic.vlan.dhcp_on = True
            nic.vlan.primary_rack = rack_controller
            nic.vlan.save()
            preseed = yaml.safe_load(
                compose_preseed(PRESEED_TYPE.COMMISSIONING, node))
            self.assertIn('power_state', preseed, status_name)

    def test_compose_pressed_for_testing_reboots_when_powered_on(self):
        rack_controller = factory.make_RackController()
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.TESTING,
            with_empty_script_sets=True)
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        script_set = node.current_testing_script_set
        script_set.power_state_before_transition = POWER_STATE.ON
        script_set.save()
        preseed = yaml.safe_load(
            compose_preseed(PRESEED_TYPE.COMMISSIONING, node))
        self.assertDictEqual({
            'delay': 'now',
            'mode': 'reboot',
            'timeout': 1800,
            'condition': 'test ! -e /tmp/block-reboot',
        }, preseed['power_state'])

    def test_compose_preseed_powersoff_for_all_other_statuses(self):
        rack_controller = factory.make_RackController()
        for status, status_name in NODE_STATUS_CHOICES:
            if status in {
                    NODE_STATUS.DEPLOYING,
                    NODE_STATUS.ENTERING_RESCUE_MODE}:
                continue
            elif status == NODE_STATUS.DISK_ERASING:
                timeout = 604800
            else:
                timeout = 3600
            node = factory.make_Node(
                interface=True, status=status, power_state=POWER_STATE.OFF,
                with_empty_script_sets=True)
            nic = node.get_boot_interface()
            nic.vlan.dhcp_on = True
            nic.vlan.primary_rack = rack_controller
            nic.vlan.save()
            preseed = yaml.safe_load(
                compose_preseed(PRESEED_TYPE.COMMISSIONING, node))
            self.assertDictEqual({
                'delay': 'now',
                'mode': 'poweroff',
                'timeout': timeout,
                'condition': 'test ! -e /tmp/block-poweroff',
            }, preseed['power_state'], status_name)

    def test_compose_preseed_for_commissioning_includes_auth_tokens(self):
        rack_controller = factory.make_RackController()
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING)
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        preseed = yaml.safe_load(
            compose_preseed(PRESEED_TYPE.COMMISSIONING, node))
        maas_dict = preseed['datasource']['MAAS']
        reporting_dict = preseed['reporting']['maas']
        token = NodeKey.objects.get_token_for_node(node)
        self.assertEqual(token.consumer.key, maas_dict['consumer_key'])
        self.assertEqual(token.key, maas_dict['token_key'])
        self.assertEqual(token.secret, maas_dict['token_secret'])
        self.assertEqual(token.consumer.key, reporting_dict['consumer_key'])
        self.assertEqual(token.key, reporting_dict['token_key'])
        self.assertEqual(token.secret, reporting_dict['token_secret'])

    def test_compose_preseed_for_commissioning_includes_packages(self):
        rack_controller = factory.make_RackController()
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING)
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        preseed = yaml.safe_load(
            compose_preseed(PRESEED_TYPE.COMMISSIONING, node))
        self.assertItemsEqual([
            'python3-yaml', 'python3-oauthlib', 'freeipmi-tools', 'ipmitool',
            'sshpass'], preseed.get('packages'))

    def test_compose_preseed_with_curtin_installer(self):
        rack_controller = factory.make_RackController(url='')
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.DEPLOYING)
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        self.useFixture(RunningClusterRPCFixture())
        region_ip = factory.make_ip_address()
        expected_apt_proxy = get_apt_proxy(
            node.get_boot_rack_controller(), default_region_ip=region_ip)
        preseed = yaml.safe_load(
            compose_preseed(
                PRESEED_TYPE.CURTIN, node, default_region_ip=region_ip))

        self.assertIn('datasource', preseed)
        self.assertIn('MAAS', preseed['datasource'])
        self.assertThat(
            preseed['datasource']['MAAS'],
            KeysEqual(
                'metadata_url', 'consumer_key', 'token_key', 'token_secret'))
        self.assertDictEqual(
            {
                'delay': 'now',
                'mode': 'reboot',
                'timeout': 1800,
                'condition': 'test ! -e /tmp/block-reboot',
            }, preseed['power_state'])
        self.assertEqual(
            absolute_reverse('curtin-metadata', default_region_ip=region_ip),
            preseed['datasource']['MAAS']['metadata_url'])
        self.assertSystemInfo(preseed)
        self.assertAptConfig(preseed, expected_apt_proxy)

    def test_compose_preseed_with_curtin_installer_skips_apt_proxy(self):
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

        rack_controller = factory.make_RackController()
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.READY)
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        self.useFixture(RunningClusterRPCFixture())
        Config.objects.set_config("enable_http_proxy", False)
        preseed = yaml.safe_load(
            compose_preseed(PRESEED_TYPE.CURTIN, node))

        self.assertNotIn('proxy', preseed['apt'])

    # LP: #1743966 - Test for archive key work around
    def test_compose_preseed_for_curtin_and_trusty_aptsources(self):
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

        rack_controller = factory.make_RackController()
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.READY, osystem='ubuntu',
            distro_series='trusty')
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        self.useFixture(RunningClusterRPCFixture())
        apt_proxy = get_apt_proxy(node.get_boot_rack_controller())
        preseed = yaml.safe_load(
            compose_preseed(PRESEED_TYPE.CURTIN, node))

        self.assertIn('apt_sources', preseed)
        self.assertEqual(apt_proxy, preseed['apt_proxy'])

    # LP: #1743966 - Test for archive key work around
    def test_compose_preseed_for_curtin_xenial_not_aptsources(self):
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

        rack_controller = factory.make_RackController()
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.READY, osystem='ubuntu',
            distro_series='xenial')
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        self.useFixture(RunningClusterRPCFixture())
        preseed = yaml.safe_load(
            compose_preseed(PRESEED_TYPE.CURTIN, node))

        self.assertNotIn('apt_sources', preseed)

    def test_compose_preseed_for_curtin_not_packages(self):
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

        rack_controller = factory.make_RackController()
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.DEPLOYING, osystem='ubuntu',
            distro_series='xenial')
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        self.useFixture(RunningClusterRPCFixture())
        preseed = yaml.safe_load(
            compose_preseed(PRESEED_TYPE.CURTIN, node))

        self.assertNotIn('packages', preseed)

    def test_compose_preseed_with_osystem_compose_preseed(self):
        os_name = factory.make_name('os')
        osystem = make_osystem(self, os_name, [BOOT_IMAGE_PURPOSE.XINSTALL])
        compose_preseed_orig = osystem.compose_preseed
        compose_preseed_mock = self.patch(osystem, 'compose_preseed')
        compose_preseed_mock.side_effect = compose_preseed_orig

        rack_controller = factory.make_RackController(url='')
        node = factory.make_Node(
            interface=True, osystem=os_name, status=NODE_STATUS.READY)
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        self.useFixture(RunningClusterRPCFixture())
        token = NodeKey.objects.get_token_for_node(node)
        region_ip = factory.make_ip_address()
        expected_url = absolute_reverse(
            'curtin-metadata', default_region_ip=region_ip)
        compose_preseed(
            PRESEED_TYPE.CURTIN, node, default_region_ip=region_ip)
        self.assertThat(
            compose_preseed_mock,
            MockCalledOnceWith(
                PRESEED_TYPE.CURTIN,
                (node.system_id, node.hostname),
                (token.consumer.key, token.key, token.secret),
                expected_url))

    def test_compose_preseed_propagates_NoSuchOperatingSystem(self):
        # If the cluster controller replies that the node's OS is not known to
        # it, compose_preseed() simply passes the exception up.
        os_name = factory.make_name('os')
        osystem = make_osystem(self, os_name, [BOOT_IMAGE_PURPOSE.XINSTALL])
        compose_preseed_mock = self.patch(osystem, 'compose_preseed')
        compose_preseed_mock.side_effect = NoSuchOperatingSystem
        rack_controller = factory.make_RackController()
        node = factory.make_Node(
            interface=True, osystem=os_name, status=NODE_STATUS.READY)
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()

        self.useFixture(RunningClusterRPCFixture())
        self.assertRaises(
            NoSuchOperatingSystem,
            compose_preseed, PRESEED_TYPE.CURTIN, node)

    def test_compose_preseed_propagates_NoConnectionsAvailable(self):
        # If the region does not have any connections to the node's cluster
        # controller, compose_preseed() simply passes the exception up.
        os_name = factory.make_name('os')
        make_osystem(self, os_name, [BOOT_IMAGE_PURPOSE.XINSTALL])
        make_usable_osystem(self, os_name)
        rack_controller = factory.make_RackController()
        node = factory.make_Node(
            interface=True, osystem=os_name, status=NODE_STATUS.READY)
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        self.assertRaises(
            NoConnectionsAvailable,
            compose_preseed, PRESEED_TYPE.CURTIN, node)

    def test_compose_enlistment_preseed(self):
        rack_controller = factory.make_RackController()
        url = factory.make_simple_http_url()
        apt_proxy = get_apt_proxy(rack_controller)
        preseed = yaml.safe_load(compose_enlistment_preseed(rack_controller, {
            'metadata_enlist_url': url,
            'syslog_host_port': url,
            }))
        self.assertDictEqual(
            {'MAAS': {'metadata_url': url}}, preseed['datasource'])
        self.assertTrue(preseed['manage_etc_hosts'])
        self.assertDictEqual({'remotes': {'maas': url}}, preseed['rsyslog'])
        self.assertDictEqual({
            'delay': 'now',
            'mode': 'poweroff',
            'timeout': 1800,
            'condition': 'test ! -e /tmp/block-poweroff',
            }, preseed['power_state'])
        self.assertItemsEqual([
            'python3-yaml', 'python3-oauthlib', 'freeipmi-tools', 'ipmitool',
            'sshpass'], preseed['packages'])
        self.assertSystemInfo(preseed)
        default = PackageRepository.get_main_archive().url
        ports = PackageRepository.get_ports_archive().url
        self.assertThat(preseed, ContainsDict({
            'apt': ContainsDict({
                'preserve_sources_list': Equals(False),
                'primary': MatchesListwise([
                    MatchesDict({
                        "arches": Equals(["amd64", "i386"]),
                        "uri": Equals(default),
                    }),
                    MatchesDict({
                        "arches": Equals(["default"]),
                        "uri": Equals(ports),
                    }),
                ]),
                'proxy': Equals(apt_proxy),
                'security': MatchesListwise([
                    MatchesDict({
                        "arches": Equals(["amd64", "i386"]),
                        "uri": Equals(default),
                    }),
                    MatchesDict({
                        "arches": Equals(["default"]),
                        "uri": Equals(ports),
                    }),
                ]),
            })
        }))

    def test_compose_enlistment_preseed_has_header(self):
        rack_controller = factory.make_RackController()
        url = factory.make_simple_http_url()
        preseed = compose_enlistment_preseed(rack_controller, {
            'metadata_enlist_url': url,
            'syslog_host_port': url,
            })
        self.assertThat(preseed, StartsWith("#cloud-config\n"))
