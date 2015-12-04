# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.compose_preseed`."""

__all__ = []

from maasserver.compose_preseed import (
    compose_preseed,
    get_apt_proxy_for_node,
)
from maasserver.enum import (
    NODE_BOOT,
    NODE_STATUS,
    PRESEED_TYPE,
)
from maasserver.models.config import Config
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


class TestComposePreseed(MAASServerTestCase):

    def assertSystemInfo(self, config):
        self.assertThat(config, ContainsDict({
            'system_info': MatchesDict({
                'package_mirrors': MatchesListwise([
                    MatchesDict({
                        "arches": Equals(["i386", "amd64"]),
                        "search": MatchesDict({
                            "primary": Equals(
                                [Config.objects.get_config("main_archive")]),
                            "security": Equals(
                                [Config.objects.get_config("main_archive")]),
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
                                [Config.objects.get_config("ports_archive")]),
                            "security": Equals(
                                [Config.objects.get_config("ports_archive")]),
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

    def test_compose_preseed_for_commissioning_node_skips_apt_proxy(self):
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        Config.objects.set_config("enable_http_proxy", False)
        preseed = yaml.safe_load(
            compose_preseed(PRESEED_TYPE.COMMISSIONING, node))
        self.assertNotIn('apt_proxy', preseed)

    def test_compose_preseed_for_commissioning_node_produces_yaml(self):
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        apt_proxy = get_apt_proxy_for_node(node)
        preseed = yaml.safe_load(
            compose_preseed(PRESEED_TYPE.COMMISSIONING, node))
        self.assertIn('datasource', preseed)
        self.assertIn('MAAS', preseed['datasource'])
        self.assertThat(
            preseed['datasource']['MAAS'],
            KeysEqual(
                'metadata_url', 'consumer_key', 'token_key', 'token_secret'))
        self.assertEqual(apt_proxy, preseed['apt_proxy'])
        self.assertThat(
            preseed['reporting']['maas'],
            KeysEqual(
                'consumer_key', 'endpoint', 'token_key', 'token_secret',
                'type'))
        self.assertSystemInfo(preseed)

    def test_compose_preseed_for_commissioning_node_has_header(self):
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        preseed = compose_preseed(PRESEED_TYPE.COMMISSIONING, node)
        self.assertThat(preseed, StartsWith("#cloud-config\n"))

    def test_compose_preseed_includes_metadata_url(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        node.nodegroup.accept()
        self.useFixture(RunningClusterRPCFixture())
        preseed = compose_preseed(PRESEED_TYPE.DEFAULT, node)
        reverse = absolute_reverse('metadata')
        self.assertIn(reverse, preseed)
        status = absolute_reverse('metadata-status', args=[node.system_id])
        self.assertIn(status, preseed)

    def test_compose_preseed_for_commissioning_includes_metadata_status_url(
            self):
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        preseed = yaml.safe_load(
            compose_preseed(PRESEED_TYPE.COMMISSIONING, node))
        self.assertEqual(
            absolute_reverse('metadata'),
            preseed['datasource']['MAAS']['metadata_url'])
        self.assertEqual(
            absolute_reverse('metadata-status', args=[node.system_id]),
            preseed['reporting']['maas']['endpoint'])

    def test_compose_preseed_includes_node_oauth_token(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        node.nodegroup.accept()
        self.useFixture(RunningClusterRPCFixture())
        preseed = compose_preseed(PRESEED_TYPE.DEFAULT, node)
        token = NodeKey.objects.get_token_for_node(node)
        self.assertIn('oauth_consumer_key=%s' % token.consumer.key, preseed)
        self.assertIn('oauth_token_key=%s' % token.key, preseed)
        self.assertIn('oauth_token_secret=%s' % token.secret, preseed)

    def test_compose_preseed_for_commissioning_includes_auth_tokens(self):
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
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

    def test_compose_preseed_valid_local_cloud_config(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        node.nodegroup.accept()
        self.useFixture(RunningClusterRPCFixture())
        apt_proxy = get_apt_proxy_for_node(node)
        preseed = compose_preseed(PRESEED_TYPE.DEFAULT, node)

        keyname = "cloud-init/local-cloud-config"
        self.assertIn(keyname, preseed)

        # Expected input is 'cloud-init/local-cloud-config string VALUE'
        # where one or more spaces in between tokens, and VALUE ending
        # at newline.
        config = preseed[preseed.find(keyname) + len(keyname):]
        value = config.lstrip().split("string")[1].lstrip()

        # Now debconf-unescape it.
        value = value.replace("\\n", "\n").replace("\\\\", "\\")

        # At this point it should be valid yaml.
        data = yaml.safe_load(value)

        self.assertIn("manage_etc_hosts", data)
        self.assertFalse(data["manage_etc_hosts"])
        self.assertIn("apt_preserve_sources_list", data)
        self.assertTrue(data["apt_preserve_sources_list"])
        self.assertEqual(apt_proxy, data["apt_proxy"])
        self.assertTrue(data["manual_cache_clean"])
        self.assertSystemInfo(data)

    def test_compose_preseed_skips_apt_proxy(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        node.nodegroup.accept()
        self.useFixture(RunningClusterRPCFixture())
        Config.objects.set_config("enable_http_proxy", False)
        preseed = compose_preseed(PRESEED_TYPE.DEFAULT, node)
        self.assertNotIn('apt_proxy', preseed)

    def test_compose_preseed_with_curtin_installer(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, boot_type=NODE_BOOT.FASTPATH)
        node.nodegroup.accept()
        self.useFixture(RunningClusterRPCFixture())
        apt_proxy = get_apt_proxy_for_node(node)
        preseed = yaml.safe_load(
            compose_preseed(PRESEED_TYPE.CURTIN, node))

        self.assertIn('datasource', preseed)
        self.assertIn('MAAS', preseed['datasource'])
        self.assertThat(
            preseed['datasource']['MAAS'],
            KeysEqual(
                'metadata_url', 'consumer_key', 'token_key', 'token_secret'))
        self.assertEqual(
            absolute_reverse('curtin-metadata'),
            preseed['datasource']['MAAS']['metadata_url'])
        self.assertEqual(apt_proxy, preseed['apt_proxy'])
        self.assertSystemInfo(preseed)

    def test_compose_preseed_with_curtin_installer_skips_apt_proxy(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, boot_type=NODE_BOOT.FASTPATH)
        node.nodegroup.accept()
        self.useFixture(RunningClusterRPCFixture())
        Config.objects.set_config("enable_http_proxy", False)
        preseed = yaml.safe_load(
            compose_preseed(PRESEED_TYPE.CURTIN, node))

        self.assertNotIn('apt_proxy', preseed)

    def test_compose_preseed_with_osystem_compose_preseed(self):
        os_name = factory.make_name('os')
        osystem = make_osystem(self, os_name, [BOOT_IMAGE_PURPOSE.XINSTALL])
        make_usable_osystem(self, os_name)
        compose_preseed_orig = osystem.compose_preseed
        compose_preseed_mock = self.patch(osystem, 'compose_preseed')
        compose_preseed_mock.side_effect = compose_preseed_orig

        node = factory.make_Node(
            osystem=os_name, status=NODE_STATUS.READY)
        node.nodegroup.accept()
        self.useFixture(RunningClusterRPCFixture())
        token = NodeKey.objects.get_token_for_node(node)
        url = absolute_reverse('curtin-metadata')
        compose_preseed(PRESEED_TYPE.CURTIN, node)
        self.assertThat(
            compose_preseed_mock,
            MockCalledOnceWith(
                PRESEED_TYPE.CURTIN,
                (node.system_id, node.hostname),
                (token.consumer.key, token.key, token.secret),
                url))

    def test_compose_preseed_propagates_NoSuchOperatingSystem(self):
        # If the cluster controller replies that the node's OS is not known to
        # it, compose_preseed() simply passes the exception up.
        os_name = factory.make_name('os')
        osystem = make_osystem(self, os_name, [BOOT_IMAGE_PURPOSE.XINSTALL])
        make_usable_osystem(self, os_name)
        compose_preseed_mock = self.patch(osystem, 'compose_preseed')
        compose_preseed_mock.side_effect = NoSuchOperatingSystem
        node = factory.make_Node(
            osystem=os_name, status=NODE_STATUS.READY)
        node.nodegroup.accept()
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
        node = factory.make_Node(
            osystem=os_name, status=NODE_STATUS.READY)
        self.assertRaises(
            NoConnectionsAvailable,
            compose_preseed, PRESEED_TYPE.CURTIN, node)
