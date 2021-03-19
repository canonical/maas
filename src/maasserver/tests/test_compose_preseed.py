# Copyright 2012-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import random

from django.urls import reverse
from testtools.matchers import (
    ContainsDict,
    Equals,
    KeysEqual,
    MatchesDict,
    MatchesListwise,
    StartsWith,
)
import yaml

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
from maastesting.http import make_HttpRequest
from maastesting.matchers import MockCalledOnceWith
from metadataserver.models import NodeKey
from provisioningserver.drivers.osystem import BOOT_IMAGE_PURPOSE
from provisioningserver.rpc.exceptions import (
    NoConnectionsAvailable,
    NoSuchOperatingSystem,
)
from provisioningserver.testing.os import make_osystem


class TestAptProxy(MAASServerTestCase):

    scenarios = (
        (
            "ipv6",
            dict(
                default_region_ip=None,
                rack="2001:db8::1",
                maas_proxy_port="",
                result="http://[2001:db8::1]:8000/",
                enable=True,
                use_peer_proxy=False,
                http_proxy="",
                use_rack_proxy=False,
                boot_cluster_ip=None,
            ),
        ),
        (
            "ipv4",
            dict(
                default_region_ip=None,
                rack="10.0.1.1",
                maas_proxy_port=8000,
                result="http://10.0.1.1:8000/",
                enable=True,
                use_peer_proxy=False,
                http_proxy="",
                use_rack_proxy=False,
                boot_cluster_ip=None,
            ),
        ),
        (
            "builtin",
            dict(
                default_region_ip=None,
                rack="region.example.com",
                maas_proxy_port=8000,
                result="http://region.example.com:8000/",
                enable=True,
                use_peer_proxy=False,
                http_proxy="",
                use_rack_proxy=False,
                boot_cluster_ip=None,
            ),
        ),
        (
            "external",
            dict(
                default_region_ip=None,
                rack="region.example.com",
                maas_proxy_port="",
                result="http://proxy.example.com:111/",
                enable=True,
                use_peer_proxy=False,
                http_proxy="http://proxy.example.com:111/",
                use_rack_proxy=False,
                boot_cluster_ip=None,
            ),
        ),
        (
            "peer-proxy",
            dict(
                default_region_ip=None,
                rack="region.example.com",
                maas_proxy_port="",
                result="http://region.example.com:8000/",
                enable=True,
                use_peer_proxy=True,
                http_proxy="http://proxy.example.com:111/",
                use_rack_proxy=False,
                boot_cluster_ip=None,
            ),
        ),
        (
            "disabled",
            dict(
                default_region_ip=None,
                rack="example.com",
                maas_proxy_port=8000,
                result=None,
                enable=False,
                use_peer_proxy=False,
                http_proxy="",
                use_rack_proxy=False,
                boot_cluster_ip=None,
            ),
        ),
        # If a default IP address for the region is passed in and the rack's
        # URL is empty, the default IP address that was provided should be
        # preferred.
        (
            "ipv6_default",
            dict(
                default_region_ip="2001:db8::2",
                rack="",
                maas_proxy_port=8000,
                result="http://[2001:db8::2]:8000/",
                enable=True,
                use_peer_proxy=False,
                http_proxy="",
                use_rack_proxy=False,
                boot_cluster_ip=None,
            ),
        ),
        (
            "ipv4_default",
            dict(
                default_region_ip="10.0.1.2",
                rack="",
                maas_proxy_port=8000,
                result="http://10.0.1.2:8000/",
                enable=True,
                use_peer_proxy=False,
                http_proxy="",
                use_rack_proxy=False,
                boot_cluster_ip=None,
            ),
        ),
        (
            "builtin_default",
            dict(
                default_region_ip="region.example.com",
                rack="",
                maas_proxy_port=8000,
                result="http://region.example.com:8000/",
                enable=True,
                use_peer_proxy=False,
                http_proxy="",
                use_rack_proxy=False,
                boot_cluster_ip=None,
            ),
        ),
        (
            "external_default",
            dict(
                default_region_ip="10.0.0.1",
                rack="",
                maas_proxy_port=8000,
                result="http://proxy.example.com:111/",
                enable=True,
                use_peer_proxy=False,
                http_proxy="http://proxy.example.com:111/",
                use_rack_proxy=False,
                boot_cluster_ip=None,
            ),
        ),
        (
            "peer-proxy_default",
            dict(
                default_region_ip="region2.example.com",
                rack="",
                maas_proxy_port=8000,
                result="http://region2.example.com:8000/",
                enable=True,
                use_peer_proxy=True,
                http_proxy="http://proxy.example.com:111/",
                use_rack_proxy=False,
                boot_cluster_ip=None,
            ),
        ),
        (
            "disabled_default",
            dict(
                default_region_ip="10.0.0.1",
                rack="",
                maas_proxy_port=8000,
                result=None,
                enable=False,
                use_peer_proxy=False,
                http_proxy="",
                use_rack_proxy=False,
                boot_cluster_ip=None,
            ),
        ),
        (
            "changed-maas_proxy_port",
            dict(
                default_region_ip="region2.example.com",
                rack="",
                maas_proxy_port=9000,
                result="http://region2.example.com:9000/",
                enable=True,
                use_peer_proxy=True,
                http_proxy="http://proxy.example.com:111/",
                use_rack_proxy=False,
                boot_cluster_ip=None,
            ),
        ),
        (
            "rack-proxy",
            dict(
                default_region_ip="",
                rack="",
                maas_proxy_port=9000,
                result="http://192-168-122-0--24.maas-internal:9000/",
                enable=True,
                use_peer_proxy=False,
                http_proxy="",
                use_rack_proxy=True,
                cidr="192.168.122.0/24",
                subnet_dns=None,
                dhcp_on=True,
                boot_cluster_ip=None,
            ),
        ),
        (
            "rack-proxy-no-subnet",
            dict(
                default_region_ip="region.example.com",
                rack="",
                maas_proxy_port=8000,
                result="http://region.example.com:8000/",
                enable=True,
                use_peer_proxy=False,
                http_proxy="",
                use_rack_proxy=True,
                cidr=None,
                subnet_dns=None,
                dhcp_on=True,
                boot_cluster_ip=None,
            ),
        ),
        (
            "rack-proxy-subnet-with-dns",
            dict(
                default_region_ip="region.example.com",
                rack="",
                maas_proxy_port=8000,
                result="http://region.example.com:8000/",
                enable=True,
                use_peer_proxy=False,
                http_proxy="",
                use_rack_proxy=True,
                cidr="192.168.122.0/24",
                subnet_dns="192.168.122.10",
                dhcp_on=True,
                boot_cluster_ip=None,
            ),
        ),
        (
            "rack-proxy-no-dhcp-through-rack",
            dict(
                default_region_ip="region.example.com",
                rack="",
                maas_proxy_port=8000,
                result="http://192.168.122.5:8000/",
                enable=True,
                use_peer_proxy=False,
                http_proxy="",
                use_rack_proxy=True,
                cidr="192.168.122.0/24",
                subnet_dns=None,
                dhcp_on=False,
                boot_cluster_ip="192.168.122.5",
            ),
        ),
    )

    def test_returns_correct_url(self):
        import maasserver.compose_preseed as cp_module

        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()
        # Force the server host to be our test data.
        self.patch(cp_module, "get_maas_facing_server_host").return_value = (
            self.rack if self.rack else self.default_region_ip
        )
        # Now setup the configuration and arguments, and see what we get back.
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING
        )
        if self.boot_cluster_ip is not None:
            node.boot_cluster_ip = self.boot_cluster_ip
            node.save()
        Config.objects.set_config("enable_http_proxy", self.enable)
        Config.objects.set_config("http_proxy", self.http_proxy)
        Config.objects.set_config("use_peer_proxy", self.use_peer_proxy)
        Config.objects.set_config("use_rack_proxy", self.use_rack_proxy)
        if self.maas_proxy_port:
            Config.objects.set_config("maas_proxy_port", self.maas_proxy_port)
        request = make_HttpRequest(http_host=self.default_region_ip)
        if self.use_rack_proxy:
            subnet = None
            if self.cidr:
                vlan = factory.make_VLAN()
                if self.dhcp_on:
                    rack = factory.make_RackController()
                    vlan.dhcp_on = True
                    vlan.primary_rack = rack
                    vlan.save()
                subnet = factory.make_Subnet(cidr=self.cidr, vlan=vlan)
                if self.subnet_dns:
                    subnet.dns_servers = [self.subnet_dns]
                else:
                    subnet.dns_servers = []
                subnet.save()
                request.META["REMOTE_ADDR"] = factory.pick_ip_in_Subnet(subnet)
            else:
                request.META["REMOTE_ADDR"] = factory.make_ipv4_address()
        actual = get_apt_proxy(request, node.get_boot_rack_controller(), node)
        self.assertEqual(self.result, actual)


class TestComposePreseed(MAASServerTestCase):
    def assertSystemInfo(self, config):
        self.assertThat(
            config,
            ContainsDict(
                {
                    "system_info": MatchesDict(
                        {
                            "package_mirrors": MatchesListwise(
                                [
                                    MatchesDict(
                                        {
                                            "arches": Equals(
                                                ["i386", "amd64"]
                                            ),
                                            "search": MatchesDict(
                                                {
                                                    "primary": Equals(
                                                        [
                                                            PackageRepository.get_main_archive().url
                                                        ]
                                                    ),
                                                    "security": Equals(
                                                        [
                                                            PackageRepository.get_main_archive().url
                                                        ]
                                                    ),
                                                }
                                            ),
                                            "failsafe": MatchesDict(
                                                {
                                                    "primary": Equals(
                                                        "http://archive.ubuntu.com/ubuntu"
                                                    ),
                                                    "security": Equals(
                                                        "http://security.ubuntu.com/ubuntu"
                                                    ),
                                                }
                                            ),
                                        }
                                    ),
                                    MatchesDict(
                                        {
                                            "arches": Equals(["default"]),
                                            "search": MatchesDict(
                                                {
                                                    "primary": Equals(
                                                        [
                                                            PackageRepository.get_ports_archive().url
                                                        ]
                                                    ),
                                                    "security": Equals(
                                                        [
                                                            PackageRepository.get_ports_archive().url
                                                        ]
                                                    ),
                                                }
                                            ),
                                            "failsafe": MatchesDict(
                                                {
                                                    "primary": Equals(
                                                        "http://ports.ubuntu.com/ubuntu-ports"
                                                    ),
                                                    "security": Equals(
                                                        "http://ports.ubuntu.com/ubuntu-ports"
                                                    ),
                                                }
                                            ),
                                        }
                                    ),
                                ]
                            )
                        }
                    )
                }
            ),
        )

    def assertAptConfig(self, config, apt_proxy):
        archive = PackageRepository.objects.get_default_archive("amd64")
        components = set(archive.KNOWN_COMPONENTS)

        if archive.disabled_components:
            for comp in archive.COMPONENTS_TO_DISABLE:
                if comp in archive.disabled_components:
                    components.remove(comp)

        components = " ".join(components)
        sources_list = "deb %s $RELEASE %s\n" % (archive.url, components)
        if archive.disable_sources:
            sources_list += "# "
        sources_list += "deb-src %s $RELEASE %s\n" % (archive.url, components)

        for pocket in archive.POCKETS_TO_DISABLE:
            if pocket in archive.disabled_pockets:
                continue
            sources_list += "deb %s $RELEASE-%s %s\n" % (
                archive.url,
                pocket,
                components,
            )
            if archive.disable_sources:
                sources_list += "# "
            sources_list += "deb-src %s $RELEASE-%s %s\n" % (
                archive.url,
                pocket,
                components,
            )

        self.assertThat(
            config,
            ContainsDict(
                {
                    "apt": ContainsDict(
                        {
                            "preserve_sources_list": Equals(False),
                            "proxy": Equals(apt_proxy),
                            "sources_list": Equals(sources_list),
                        }
                    )
                }
            ),
        )
        self.assertEqual(
            config["snap"],
            {
                "commands": [
                    f'snap set system proxy.http="{apt_proxy}" proxy.https="{apt_proxy}"',
                ],
            },
        )

    def test_compose_preseed_for_commissioning_node_skips_apt_proxy(self):
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

        rack_controller = factory.make_RackController()
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING
        )
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        Config.objects.set_config("enable_http_proxy", False)
        request = make_HttpRequest()
        preseed = yaml.safe_load(
            compose_preseed(request, PRESEED_TYPE.COMMISSIONING, node)
        )
        self.assertNotIn("proxy", preseed["apt"])

    def test_compose_preseed_for_commissioning_node_produces_yaml(self):
        rack_controller = factory.make_RackController()
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING
        )
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        request = make_HttpRequest()
        apt_proxy = get_apt_proxy(request, node.get_boot_rack_controller())
        preseed = yaml.safe_load(
            compose_preseed(request, PRESEED_TYPE.COMMISSIONING, node)
        )
        self.assertIn("datasource", preseed)
        self.assertIn("MAAS", preseed["datasource"])
        self.assertThat(
            preseed["datasource"]["MAAS"],
            KeysEqual(
                "metadata_url", "consumer_key", "token_key", "token_secret"
            ),
        )
        self.assertThat(
            preseed["reporting"]["maas"],
            KeysEqual(
                "consumer_key", "endpoint", "token_key", "token_secret", "type"
            ),
        )
        self.assertThat(preseed["rsyslog"]["remotes"], KeysEqual("maas"))
        self.assertAptConfig(preseed, apt_proxy)
        self.assertEqual(
            preseed["snap"],
            {
                "commands": [
                    f'snap set system proxy.http="{apt_proxy}" proxy.https="{apt_proxy}"',
                ],
            },
        )

    def test_compose_preseed_for_commissioning_node_has_header(self):
        rack_controller = factory.make_RackController()
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING
        )
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        request = make_HttpRequest()
        preseed = compose_preseed(request, PRESEED_TYPE.COMMISSIONING, node)
        self.assertThat(preseed, StartsWith("#cloud-config\n"))

    def test_compose_preseed_for_commissioning_node_manages_etc_hosts(self):
        # Regression test for LP:1670444
        rack_controller = factory.make_RackController()
        node = factory.make_Node(
            interface=True,
            status=random.choice(
                [
                    NODE_STATUS.COMMISSIONING,
                    NODE_STATUS.TESTING,
                    NODE_STATUS.RESCUE_MODE,
                ]
            ),
            with_empty_script_sets=True,
        )
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        request = make_HttpRequest()
        preseed = yaml.safe_load(
            compose_preseed(request, PRESEED_TYPE.COMMISSIONING, node)
        )
        self.assertTrue(preseed["manage_etc_hosts"])

    def test_compose_preseed_for_commissioning_includes_metadata_status_url(
        self,
    ):
        rack_controller = factory.make_RackController(url="")
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING
        )
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        request = make_HttpRequest()
        preseed = yaml.safe_load(
            compose_preseed(request, PRESEED_TYPE.COMMISSIONING, node)
        )
        self.assertEqual(
            request.build_absolute_uri(reverse("metadata")),
            preseed["datasource"]["MAAS"]["metadata_url"],
        )
        self.assertEqual(
            request.build_absolute_uri(
                reverse("metadata-status", args=[node.system_id])
            ),
            preseed["reporting"]["maas"]["endpoint"],
        )

    def test_compose_preseed_uses_request_build_absolute_uri(self):
        rack_controller = factory.make_RackController(url="")
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING
        )
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        request = make_HttpRequest()
        preseed = yaml.safe_load(
            compose_preseed(request, PRESEED_TYPE.COMMISSIONING, node)
        )
        self.assertEqual(
            request.build_absolute_uri(reverse("metadata")),
            preseed["datasource"]["MAAS"]["metadata_url"],
        )
        self.assertEqual(
            request.build_absolute_uri(
                reverse("metadata-status", args=[node.system_id])
            ),
            preseed["reporting"]["maas"]["endpoint"],
        )

    def test_compose_preseed_uses_remote_syslog(self):
        remote_syslog = "192.168.1.1:514"
        Config.objects.set_config("remote_syslog", remote_syslog)
        rack_controller = factory.make_RackController(url="")
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING
        )
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        request = make_HttpRequest()
        preseed = yaml.safe_load(
            compose_preseed(request, PRESEED_TYPE.COMMISSIONING, node)
        )
        self.assertEqual(remote_syslog, preseed["rsyslog"]["remotes"]["maas"])

    def test_compose_preseed_uses_maas_syslog_port(self):
        syslog_port = factory.pick_port()
        Config.objects.set_config("maas_syslog_port", syslog_port)
        rack_controller = factory.make_RackController(url="")
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING
        )
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        ip_address = factory.make_ipv4_address()
        node.boot_cluster_ip = ip_address
        node.save()
        request = make_HttpRequest()
        preseed = yaml.safe_load(
            compose_preseed(request, PRESEED_TYPE.COMMISSIONING, node)
        )
        self.assertEqual(
            "%s:%d" % (ip_address, syslog_port),
            preseed["rsyslog"]["remotes"]["maas"],
        )

    def test_compose_preseed_for_rescue_mode_does_not_include_poweroff(self):
        rack_controller = factory.make_RackController()
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.ENTERING_RESCUE_MODE
        )
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        request = make_HttpRequest()
        preseed = yaml.safe_load(
            compose_preseed(request, PRESEED_TYPE.COMMISSIONING, node)
        )
        self.assertNotIn("power_state", preseed)

    def test_compose_preseed_ephemeral_deployment_not_include_poweroff(self):
        # A diskless node is one that it is ephemerally deployed.
        rack_controller = factory.make_RackController()
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.ENTERING_RESCUE_MODE,
            with_boot_disk=False,
        )
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        request = make_HttpRequest()
        preseed = yaml.safe_load(
            compose_preseed(request, PRESEED_TYPE.COMMISSIONING, node)
        )
        self.assertNotIn("power_state", preseed)

    def test_compose_preseed_for_enable_ssh_does_not_include_poweroff(self):
        rack_controller = factory.make_RackController()
        for status in {NODE_STATUS.COMMISSIONING, NODE_STATUS.TESTING}:
            node = factory.make_Node(
                interface=True, status=status, enable_ssh=True
            )
            nic = node.get_boot_interface()
            nic.vlan.dhcp_on = True
            nic.vlan.primary_rack = rack_controller
            nic.vlan.save()
            request = make_HttpRequest()
            preseed = yaml.safe_load(
                compose_preseed(request, PRESEED_TYPE.COMMISSIONING, node)
            )
            self.assertNotIn("power_state", preseed)

    def test_compose_preseed_for_enable_ssh_ignored_unsupported_states(self):
        rack_controller = factory.make_RackController()
        for status, status_name in NODE_STATUS_CHOICES:
            if status in {
                NODE_STATUS.COMMISSIONING,
                NODE_STATUS.TESTING,
                NODE_STATUS.ENTERING_RESCUE_MODE,
            }:
                continue
            node = factory.make_Node(
                interface=True, status=status, enable_ssh=True
            )
            nic = node.get_boot_interface()
            nic.vlan.dhcp_on = True
            nic.vlan.primary_rack = rack_controller
            nic.vlan.save()
            request = make_HttpRequest()
            preseed = yaml.safe_load(
                compose_preseed(request, PRESEED_TYPE.COMMISSIONING, node)
            )
            self.assertIn("power_state", preseed, status_name)

    def test_compose_pressed_for_testing_reboots_when_powered_on(self):
        rack_controller = factory.make_RackController()
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.TESTING,
            with_empty_script_sets=True,
        )
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        script_set = node.current_testing_script_set
        script_set.power_state_before_transition = POWER_STATE.ON
        script_set.save()
        request = make_HttpRequest()
        preseed = yaml.safe_load(
            compose_preseed(request, PRESEED_TYPE.COMMISSIONING, node)
        )
        self.assertDictEqual(
            {
                "delay": "now",
                "mode": "reboot",
                "timeout": 1800,
                "condition": "test ! -e /tmp/block-reboot",
            },
            preseed["power_state"],
        )

    def test_compose_preseed_powersoff_for_all_other_statuses(self):
        rack_controller = factory.make_RackController()
        for status, status_name in NODE_STATUS_CHOICES:
            if status in {
                NODE_STATUS.DEPLOYING,
                NODE_STATUS.ENTERING_RESCUE_MODE,
            }:
                continue
            elif status == NODE_STATUS.DISK_ERASING:
                timeout = 604800
            else:
                timeout = 3600
            node = factory.make_Node(
                interface=True,
                status=status,
                power_state=POWER_STATE.OFF,
                with_empty_script_sets=True,
            )
            nic = node.get_boot_interface()
            nic.vlan.dhcp_on = True
            nic.vlan.primary_rack = rack_controller
            nic.vlan.save()
            request = make_HttpRequest()
            preseed = yaml.safe_load(
                compose_preseed(request, PRESEED_TYPE.COMMISSIONING, node)
            )
            self.assertDictEqual(
                {
                    "delay": "now",
                    "mode": "poweroff",
                    "timeout": timeout,
                    "condition": "test ! -e /tmp/block-poweroff",
                },
                preseed["power_state"],
                status_name,
            )

    def test_compose_preseed_for_commissioning_includes_auth_tokens(self):
        rack_controller = factory.make_RackController()
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING
        )
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        request = make_HttpRequest()
        preseed = yaml.safe_load(
            compose_preseed(request, PRESEED_TYPE.COMMISSIONING, node)
        )
        maas_dict = preseed["datasource"]["MAAS"]
        reporting_dict = preseed["reporting"]["maas"]
        token = NodeKey.objects.get_token_for_node(node)
        self.assertEqual(token.consumer.key, maas_dict["consumer_key"])
        self.assertEqual(token.key, maas_dict["token_key"])
        self.assertEqual(token.secret, maas_dict["token_secret"])
        self.assertEqual(token.consumer.key, reporting_dict["consumer_key"])
        self.assertEqual(token.key, reporting_dict["token_key"])
        self.assertEqual(token.secret, reporting_dict["token_secret"])

    def test_compose_preseed_for_commissioning_includes_packages(self):
        rack_controller = factory.make_RackController()
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING
        )
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        request = make_HttpRequest()
        preseed = yaml.safe_load(
            compose_preseed(request, PRESEED_TYPE.COMMISSIONING, node)
        )
        self.assertItemsEqual(
            [
                "python3-yaml",
                "python3-oauthlib",
            ],
            preseed.get("packages"),
        )

    def test_compose_preseed_with_curtin_installer(self):
        rack_controller = factory.make_RackController(url="")
        node = factory.make_Node(interface=True, status=NODE_STATUS.DEPLOYING)
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        self.useFixture(RunningClusterRPCFixture())
        request = make_HttpRequest()
        expected_apt_proxy = get_apt_proxy(
            request, node.get_boot_rack_controller()
        )
        preseed = yaml.safe_load(
            compose_preseed(request, PRESEED_TYPE.CURTIN, node)
        )

        self.assertIn("datasource", preseed)
        self.assertIn("MAAS", preseed["datasource"])
        self.assertThat(
            preseed["datasource"]["MAAS"],
            KeysEqual(
                "metadata_url", "consumer_key", "token_key", "token_secret"
            ),
        )
        self.assertDictEqual(
            {
                "delay": "now",
                "mode": "reboot",
                "timeout": 1800,
                "condition": "test ! -e /tmp/block-reboot",
            },
            preseed["power_state"],
        )
        self.assertEqual(
            request.build_absolute_uri(reverse("curtin-metadata")),
            preseed["datasource"]["MAAS"]["metadata_url"],
        )
        self.assertAptConfig(preseed, expected_apt_proxy)
        self.assertEqual(
            preseed["snap"],
            {
                "commands": [
                    f'snap set system proxy.http="{expected_apt_proxy}" proxy.https="{expected_apt_proxy}"',
                ],
            },
        )

    def test_compose_preseed_with_curtin_installer_skips_apt_proxy(self):
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

        rack_controller = factory.make_RackController()
        node = factory.make_Node(interface=True, status=NODE_STATUS.READY)
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        self.useFixture(RunningClusterRPCFixture())
        Config.objects.set_config("enable_http_proxy", False)
        request = make_HttpRequest()
        preseed = yaml.safe_load(
            compose_preseed(request, PRESEED_TYPE.CURTIN, node)
        )

        self.assertNotIn("proxy", preseed["apt"])
        self.assertNotIn("snap", preseed)

    # LP: #1743966 - Test for archive key work around
    def test_compose_preseed_for_curtin_and_trusty_aptsources(self):
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

        rack_controller = factory.make_RackController()
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.READY,
            osystem="ubuntu",
            distro_series="trusty",
        )
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        self.useFixture(RunningClusterRPCFixture())
        request = make_HttpRequest()
        apt_proxy = get_apt_proxy(request, node.get_boot_rack_controller())
        preseed = yaml.safe_load(
            compose_preseed(request, PRESEED_TYPE.CURTIN, node)
        )

        self.assertIn("apt_sources", preseed)
        self.assertEqual(apt_proxy, preseed["apt_proxy"])
        self.assertSystemInfo(preseed)

    # LP: #1743966 - Precise is now deployed on a commissioning environment
    # (e.g. Xenial/Bionic), so it no longer needs the workaround that
    # the bug report addresses.
    def test_compose_preseed_for_curtin_precise_not_aptsources(self):
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

        rack_controller = factory.make_RackController()
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.READY,
            osystem="ubuntu",
            distro_series="precise",
        )
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        self.useFixture(RunningClusterRPCFixture())
        request = make_HttpRequest()
        preseed = yaml.safe_load(
            compose_preseed(request, PRESEED_TYPE.CURTIN, node)
        )

        self.assertNotIn("apt_sources", preseed)

    def test_compose_preseed_for_curtin_not_packages(self):
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

        rack_controller = factory.make_RackController()
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.DEPLOYING,
            osystem="ubuntu",
            distro_series="xenial",
        )
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        self.useFixture(RunningClusterRPCFixture())
        request = make_HttpRequest()
        preseed = yaml.safe_load(
            compose_preseed(request, PRESEED_TYPE.CURTIN, node)
        )

        self.assertNotIn("packages", preseed)

    def test_compose_preseed_with_osystem_compose_preseed(self):
        os_name = factory.make_name("os")
        osystem = make_osystem(self, os_name, [BOOT_IMAGE_PURPOSE.XINSTALL])
        compose_preseed_orig = osystem.compose_preseed
        compose_preseed_mock = self.patch(osystem, "compose_preseed")
        compose_preseed_mock.side_effect = compose_preseed_orig

        rack_controller = factory.make_RackController(url="")
        node = factory.make_Node(
            interface=True, osystem=os_name, status=NODE_STATUS.READY
        )
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        self.useFixture(RunningClusterRPCFixture())
        token = NodeKey.objects.get_token_for_node(node)
        request = make_HttpRequest()
        expected_url = request.build_absolute_uri(reverse("curtin-metadata"))
        compose_preseed(request, PRESEED_TYPE.CURTIN, node)
        self.assertThat(
            compose_preseed_mock,
            MockCalledOnceWith(
                PRESEED_TYPE.CURTIN,
                (node.system_id, node.hostname),
                (token.consumer.key, token.key, token.secret),
                expected_url,
            ),
        )

    def test_compose_preseed_propagates_NoSuchOperatingSystem(self):
        # If the cluster controller replies that the node's OS is not known to
        # it, compose_preseed() simply passes the exception up.
        os_name = factory.make_name("os")
        osystem = make_osystem(self, os_name, [BOOT_IMAGE_PURPOSE.XINSTALL])
        compose_preseed_mock = self.patch(osystem, "compose_preseed")
        compose_preseed_mock.side_effect = NoSuchOperatingSystem
        rack_controller = factory.make_RackController()
        node = factory.make_Node(
            interface=True, osystem=os_name, status=NODE_STATUS.READY
        )
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()

        self.useFixture(RunningClusterRPCFixture())
        self.assertRaises(
            NoSuchOperatingSystem,
            compose_preseed,
            make_HttpRequest(),
            PRESEED_TYPE.CURTIN,
            node,
        )

    def test_compose_preseed_propagates_NoConnectionsAvailable(self):
        # If the region does not have any connections to the node's cluster
        # controller, compose_preseed() simply passes the exception up.
        os_name = factory.make_name("os")
        make_osystem(self, os_name, [BOOT_IMAGE_PURPOSE.XINSTALL])
        make_usable_osystem(self, os_name)
        rack_controller = factory.make_RackController()
        node = factory.make_Node(
            interface=True, osystem=os_name, status=NODE_STATUS.READY
        )
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller
        nic.vlan.save()
        self.assertRaises(
            NoConnectionsAvailable,
            compose_preseed,
            make_HttpRequest(),
            PRESEED_TYPE.CURTIN,
            node,
        )

    def test_compose_enlistment_preseed(self):
        rack_controller = factory.make_RackController()
        url = factory.make_simple_http_url()
        request = make_HttpRequest()
        apt_proxy = get_apt_proxy(request, rack_controller)
        preseed = yaml.safe_load(
            compose_enlistment_preseed(
                request,
                rack_controller,
                {"syslog_host_port": url},
            )
        )
        self.assertDictEqual(
            {
                "MAAS": {
                    "metadata_url": request.build_absolute_uri(
                        reverse("metadata")
                    )
                }
            },
            preseed["datasource"],
        )
        self.assertTrue(preseed["manage_etc_hosts"])
        self.assertDictEqual({"remotes": {"maas": url}}, preseed["rsyslog"])
        self.assertDictEqual(
            {
                "delay": "now",
                "mode": "poweroff",
                "timeout": 1800,
                "condition": "test ! -e /tmp/block-poweroff",
            },
            preseed["power_state"],
        )
        self.assertItemsEqual(
            [
                "python3-yaml",
                "python3-oauthlib",
            ],
            preseed["packages"],
        )
        default = PackageRepository.get_main_archive().url
        ports = PackageRepository.get_ports_archive().url
        self.assertThat(
            preseed,
            ContainsDict(
                {
                    "apt": ContainsDict(
                        {
                            "preserve_sources_list": Equals(False),
                            "primary": MatchesListwise(
                                [
                                    MatchesDict(
                                        {
                                            "arches": Equals(
                                                ["amd64", "i386"]
                                            ),
                                            "uri": Equals(default),
                                        }
                                    ),
                                    MatchesDict(
                                        {
                                            "arches": Equals(["default"]),
                                            "uri": Equals(ports),
                                        }
                                    ),
                                ]
                            ),
                            "proxy": Equals(apt_proxy),
                            "security": MatchesListwise(
                                [
                                    MatchesDict(
                                        {
                                            "arches": Equals(
                                                ["amd64", "i386"]
                                            ),
                                            "uri": Equals(default),
                                        }
                                    ),
                                    MatchesDict(
                                        {
                                            "arches": Equals(["default"]),
                                            "uri": Equals(ports),
                                        }
                                    ),
                                ]
                            ),
                        }
                    )
                }
            ),
        )

    def test_compose_enlistment_preseed_has_header(self):
        rack_controller = factory.make_RackController()
        url = factory.make_simple_http_url()
        request = make_HttpRequest()
        preseed = compose_enlistment_preseed(
            request,
            rack_controller,
            {"metadata_enlist_url": url, "syslog_host_port": url},
        )
        self.assertThat(preseed, StartsWith("#cloud-config\n"))

    def test_compose_enlistment_preseed_disables_suites(self):
        default = PackageRepository.get_main_archive()
        default.disabled_pockets = ["security", "updates", "backports"]
        default.save()
        rack_controller = factory.make_RackController()
        url = factory.make_simple_http_url()
        request = make_HttpRequest()
        preseed = yaml.safe_load(
            compose_enlistment_preseed(
                request,
                rack_controller,
                {"metadata_enlist_url": url, "syslog_host_port": url},
            )
        )
        self.assertItemsEqual(
            set(
                [
                    "#",
                    "deb",
                    "deb-src",
                    "$PRIMARY",
                    "$RELEASE",
                    "multiverse",
                    "restricted",
                    "universe",
                    "main",
                ]
            ),
            set(preseed["apt"]["sources_list"].split()),
        )

    def test_compose_enlistment_preseed_disables_components(self):
        default = PackageRepository.get_main_archive()
        default.disabled_components = ["restricted", "multiverse"]
        default.save()
        rack_controller = factory.make_RackController()
        url = factory.make_simple_http_url()
        request = make_HttpRequest()
        preseed = yaml.safe_load(
            compose_enlistment_preseed(
                request,
                rack_controller,
                {"metadata_enlist_url": url, "syslog_host_port": url},
            )
        )
        self.assertNotIn("restricted", preseed["apt"]["sources_list"])
        self.assertNotIn("multiverse", preseed["apt"]["sources_list"])
