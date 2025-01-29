# Copyright 2012-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import ip_address
import random

from django.urls import reverse
import yaml

import maasserver.compose_preseed as cp_module
from maasserver.compose_preseed import (
    build_metadata_url,
    compose_enlistment_preseed,
    compose_preseed,
    get_apt_proxy,
)
from maasserver.enum import NODE_STATUS, NODE_STATUS_CHOICES, PRESEED_TYPE
from maasserver.models import NodeKey, PackageRepository
from maasserver.models.config import Config
from maasserver.rpc.testing.fixtures import RunningClusterRPCFixture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import post_commit_hooks
from maastesting.http import make_HttpRequest
from provisioningserver.drivers.osystem import BOOT_IMAGE_PURPOSE
from provisioningserver.enum import POWER_STATE
from provisioningserver.rpc.exceptions import NoSuchOperatingSystem
from provisioningserver.testing.os import make_osystem


def _make_request(machine_ip):
    request = make_HttpRequest()
    # The rack IP in HTTP_X_FORWARDED might not be on the subnet
    # we're interested in.
    rack_proxy_ip = factory.make_ip_address()
    request.META["HTTP_X_FORWARDED_FOR"] = f"{machine_ip}, {rack_proxy_ip}"
    return request


def _enable_dhcp(subnet, primary_rack, secondary_rack=None, relay_vlan=None):
    dhcp_vlan = relay_vlan if relay_vlan else subnet.vlan
    dhcp_vlan.dhcp_on = True
    dhcp_vlan.primary_rack = primary_rack
    dhcp_vlan.secondary_rack = secondary_rack

    with post_commit_hooks:
        dhcp_vlan.save()
        if relay_vlan:
            subnet.vlan.relay_vlan = relay_vlan
            subnet.vlan.save()


class TestAptProxyScenarios(MAASServerTestCase):
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


class TestAptProxy(MAASServerTestCase):
    def test_enlist_rack_proxy_dhcp_relay(self):
        Config.objects.set_config("enable_http_proxy", True)
        Config.objects.set_config("use_peer_proxy", False)
        Config.objects.set_config("use_rack_proxy", True)

        subnet1 = factory.make_Subnet(cidr="10.10.0.0/24", dns_servers=[])
        subnet2 = factory.make_Subnet(cidr="10.20.0.0/24", dns_servers=[])
        rack = factory.make_rack_with_interfaces(eth0=["10.10.0.2/24"])
        _enable_dhcp(subnet2, rack, relay_vlan=subnet1.vlan)
        machine_ip = "10.20.0.100"
        apt_proxy = get_apt_proxy(_make_request(machine_ip), rack, node=None)
        self.assertEqual("http://10-10-0-0--24.maas-internal:8000/", apt_proxy)

    def test_enlist_rack_proxy(self):
        Config.objects.set_config("enable_http_proxy", True)
        Config.objects.set_config("use_peer_proxy", False)
        Config.objects.set_config("use_rack_proxy", True)

        subnet1 = factory.make_Subnet(cidr="10.10.0.0/24", dns_servers=[])
        rack = factory.make_rack_with_interfaces(eth0=["10.10.0.2/24"])
        _enable_dhcp(subnet1, rack)
        machine_ip = "10.10.0.100"
        apt_proxy = get_apt_proxy(_make_request(machine_ip), rack, node=None)
        self.assertEqual("http://10-10-0-0--24.maas-internal:8000/", apt_proxy)

    def test_enlist_rack_proxy_with_dns(self):
        Config.objects.set_config("enable_http_proxy", True)
        Config.objects.set_config("use_peer_proxy", False)
        Config.objects.set_config("use_rack_proxy", True)

        subnet1 = factory.make_Subnet(
            cidr="10.10.0.0/24", dns_servers=["10.10.0.1"]
        )
        rack = factory.make_rack_with_interfaces(eth0=["10.10.0.2/24"])
        _enable_dhcp(subnet1, rack)
        machine_ip = "10.10.0.100"
        apt_proxy = get_apt_proxy(_make_request(machine_ip), rack, node=None)
        self.assertEqual("http://10.10.0.2:8000/", apt_proxy)

    def test_enlist_rack_proxy_no_rack_subnet(self):
        Config.objects.set_config("enable_http_proxy", True)
        Config.objects.set_config("use_peer_proxy", False)
        Config.objects.set_config("use_rack_proxy", True)
        self.patch(cp_module, "get_maas_facing_server_host").return_value = (
            "region.example.com"
        )

        subnet1 = factory.make_Subnet(cidr="10.10.0.0/24", dns_servers=[])
        rack = factory.make_rack_with_interfaces(eth0=["10.10.0.2/24"])
        _enable_dhcp(subnet1, rack)
        machine_ip = "10.20.0.100"
        apt_proxy = get_apt_proxy(_make_request(machine_ip), rack, node=None)
        self.assertEqual("http://region.example.com:8000/", apt_proxy)


class TestComposePreseed(MAASServerTestCase):
    def assertSystemInfo(self, config):
        main_archive_url = PackageRepository.get_main_archive().url
        ports_archive_url = PackageRepository.get_ports_archive().url
        expected_package_mirrors = [
            {
                "arches": ["i386", "amd64"],
                "search": {
                    "primary": [main_archive_url],
                    "security": [main_archive_url],
                },
                "failsafe": {
                    "primary": "http://archive.ubuntu.com/ubuntu",
                    "security": "http://security.ubuntu.com/ubuntu",
                },
            },
            {
                "arches": ["default"],
                "search": {
                    "primary": [ports_archive_url],
                    "security": [ports_archive_url],
                },
                "failsafe": {
                    "primary": "http://ports.ubuntu.com/ubuntu-ports",
                    "security": "http://ports.ubuntu.com/ubuntu-ports",
                },
            },
        ]

        self.assertEqual(
            config.get("system_info", {}).get("package_mirrors"),
            expected_package_mirrors,
        )

    def assertAptConfig(self, config, apt_proxy):
        archive = PackageRepository.objects.get_default_archive("amd64")
        components = set(archive.KNOWN_COMPONENTS)

        if archive.disabled_components:
            for comp in archive.COMPONENTS_TO_DISABLE:
                if comp in archive.disabled_components:
                    components.remove(comp)

        components = " ".join(components)
        sources_list = f"deb {archive.url} $RELEASE {components}\n"
        if archive.disable_sources:
            sources_list += "# "
        sources_list += f"deb-src {archive.url} $RELEASE {components}\n"

        for pocket in archive.POCKETS_TO_DISABLE:
            if pocket in archive.disabled_pockets:
                continue
            sources_list += "deb {} $RELEASE-{} {}\n".format(
                archive.url,
                pocket,
                components,
            )
            if archive.disable_sources:
                sources_list += "# "
            sources_list += "deb-src {} $RELEASE-{} {}\n".format(
                archive.url,
                pocket,
                components,
            )

        self.assertEqual(
            config.get("apt", {}),
            {
                "preserve_sources_list": False,
                "proxy": apt_proxy,
                "sources_list": sources_list,
            },
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
        rack_controller = factory.make_RackController()
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING
        )
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller

        with post_commit_hooks:
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

        with post_commit_hooks:
            nic.vlan.save()
        request = make_HttpRequest()
        apt_proxy = get_apt_proxy(request, node.get_boot_rack_controller())
        preseed = yaml.safe_load(
            compose_preseed(request, PRESEED_TYPE.COMMISSIONING, node)
        )
        self.assertIn("datasource", preseed)
        self.assertIn("MAAS", preseed["datasource"])
        self.assertEqual(
            preseed["datasource"]["MAAS"].keys(),
            {"metadata_url", "consumer_key", "token_key", "token_secret"},
        )
        self.assertEqual(
            preseed["reporting"]["maas"].keys(),
            {"consumer_key", "endpoint", "token_key", "token_secret", "type"},
        )
        self.assertEqual(preseed["rsyslog"]["remotes"].keys(), {"maas"})
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

        with post_commit_hooks:
            nic.vlan.save()

        request = make_HttpRequest()
        preseed = compose_preseed(request, PRESEED_TYPE.COMMISSIONING, node)
        self.assertTrue(preseed.startswith("#cloud-config\n"))

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

        with post_commit_hooks:
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

        with post_commit_hooks:
            nic.vlan.save()

        request = make_HttpRequest()
        preseed = yaml.safe_load(
            compose_preseed(request, PRESEED_TYPE.COMMISSIONING, node)
        )
        self.assertEqual(
            f"{request.scheme}://{rack_controller.fqdn}:5248{reverse('metadata')}",
            preseed["datasource"]["MAAS"]["metadata_url"],
        )
        self.assertEqual(
            f"{request.scheme}://{rack_controller.fqdn}:5248{reverse('metadata-status', args=[node.system_id])}",
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

        with post_commit_hooks:
            nic.vlan.save()

        request = make_HttpRequest()
        preseed = yaml.safe_load(
            compose_preseed(request, PRESEED_TYPE.COMMISSIONING, node)
        )
        self.assertEqual(
            f"{request.scheme}://{rack_controller.fqdn}:5248{reverse('metadata')}",
            preseed["datasource"]["MAAS"]["metadata_url"],
        )
        self.assertEqual(
            f"{request.scheme}://{rack_controller.fqdn}:5248{reverse('metadata-status', args=[node.system_id])}",
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

        with post_commit_hooks:
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

        with post_commit_hooks:
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

        with post_commit_hooks:
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

        with post_commit_hooks:
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

            with post_commit_hooks:
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

            with post_commit_hooks:
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

        with post_commit_hooks:
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

            with post_commit_hooks:
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

        with post_commit_hooks:
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

        with post_commit_hooks:
            nic.vlan.save()

        request = make_HttpRequest()
        preseed = yaml.safe_load(
            compose_preseed(request, PRESEED_TYPE.COMMISSIONING, node)
        )
        self.assertEqual(
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

        with post_commit_hooks:
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
        self.assertEqual(
            preseed["datasource"]["MAAS"].keys(),
            {"metadata_url", "consumer_key", "token_key", "token_secret"},
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
            f"{request.scheme}://{rack_controller.fqdn}:5248{reverse('curtin-metadata')}",
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
        rack_controller = factory.make_RackController()
        node = factory.make_Node(interface=True, status=NODE_STATUS.READY)
        nic = node.get_boot_interface()
        nic.vlan.dhcp_on = True
        nic.vlan.primary_rack = rack_controller

        with post_commit_hooks:
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

        with post_commit_hooks:
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

        with post_commit_hooks:
            nic.vlan.save()

        self.useFixture(RunningClusterRPCFixture())
        request = make_HttpRequest()
        preseed = yaml.safe_load(
            compose_preseed(request, PRESEED_TYPE.CURTIN, node)
        )

        self.assertNotIn("apt_sources", preseed)

    def test_compose_preseed_for_curtin_not_packages(self):
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

        with post_commit_hooks:
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

        with post_commit_hooks:
            nic.vlan.save()

        self.useFixture(RunningClusterRPCFixture())
        token = NodeKey.objects.get_token_for_node(node)
        request = make_HttpRequest()
        expected_url = f"{request.scheme}://{rack_controller.fqdn}:5248{reverse('curtin-metadata')}"
        compose_preseed(request, PRESEED_TYPE.CURTIN, node)
        compose_preseed_mock.assert_called_once_with(
            PRESEED_TYPE.CURTIN,
            (node.system_id, node.hostname),
            (token.consumer.key, token.key, token.secret),
            expected_url,
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

        with post_commit_hooks:
            nic.vlan.save()

        self.useFixture(RunningClusterRPCFixture())
        self.assertRaises(
            NoSuchOperatingSystem,
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
                    "metadata_url": f"{request.scheme}://{rack_controller.fqdn}:5248{reverse('metadata')}",
                }
            },
            preseed["datasource"],
        )
        self.assertTrue(preseed["manage_etc_hosts"])
        self.assertEqual({"remotes": {"maas": url}}, preseed["rsyslog"])
        self.assertEqual(
            {
                "delay": "now",
                "mode": "poweroff",
                "timeout": 1800,
                "condition": "test ! -e /tmp/block-poweroff",
            },
            preseed["power_state"],
        )
        self.assertEqual(
            [
                "python3-yaml",
                "python3-oauthlib",
            ],
            preseed["packages"],
        )
        default = PackageRepository.get_main_archive().url
        ports = PackageRepository.get_ports_archive().url
        self.maxDiff = None
        apt = preseed.get("apt", {})
        # don't need to assert against this
        apt.pop("sources_list", None)
        self.assertEqual(
            preseed.get("apt"),
            {
                "preserve_sources_list": False,
                "primary": [
                    {
                        "arches": ["amd64", "i386"],
                        "uri": default,
                    },
                    {
                        "arches": ["default"],
                        "uri": ports,
                    },
                ],
                "proxy": apt_proxy,
                "security": [
                    {
                        "arches": ["amd64", "i386"],
                        "uri": default,
                    },
                    {
                        "arches": ["default"],
                        "uri": ports,
                    },
                ],
            },
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
        self.assertTrue(preseed.startswith("#cloud-config\n"))

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
        self.assertEqual(
            {
                "#",
                "deb",
                "deb-src",
                "$PRIMARY",
                "$RELEASE",
                "multiverse",
                "restricted",
                "universe",
                "main",
            },
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

    def test_compose_enlistment_preseed_uses_rack_controller_url(self):
        rack_controller = factory.make_RackController()
        request = make_HttpRequest()
        url = factory.make_simple_http_url()
        preseed = yaml.safe_load(
            compose_enlistment_preseed(
                request,
                rack_controller,
                {"metadata_enlist_url": url, "syslog_host_port": url},
            )
        )
        self.assertEqual(
            f"http://{rack_controller.fqdn}:5248/MAAS/metadata/",
            preseed["datasource"]["MAAS"]["metadata_url"],
        )


class TestBuildMetadataURL(MAASServerTestCase):
    def test_build_metadata_url_uses_original_request(self):
        request = make_HttpRequest()
        route = "/MAAS"
        self.assertEqual(
            build_metadata_url(request, route, None),
            request.build_absolute_uri(route),
        )

    def test_build_metadata_url_uses_rack_controller_fqdn(self):
        node = factory.make_Node()
        controller = factory.make_RackController()
        request = make_HttpRequest()
        route = "/MAAS"
        self.assertEqual(
            f"{request.scheme}://{controller.fqdn}:5248/MAAS",
            build_metadata_url(request, route, controller, node=node),
        )

    def test_build_metadata_url_uses_node_boot_cluster_ip(self):
        node = factory.make_Node_with_Interface_on_Subnet()
        node.boot_cluster_ip = factory.make_ip_address()
        node.save()
        request = make_HttpRequest()
        route = "/MAAS"
        host = (
            node.boot_cluster_ip
            if ip_address(node.boot_cluster_ip).version == 4
            else f"[{node.boot_cluster_ip}]"
        )
        self.assertEqual(
            f"{request.scheme}://{host}:5248/MAAS",
            build_metadata_url(
                request, route, node.get_boot_rack_controller(), node=node
            ),
        )

    def test_build_metadata_url_appends_extra(self):
        node = factory.make_Node_with_Interface_on_Subnet()
        node.boot_cluster_ip = factory.make_ip_address()
        node.save()
        request = make_HttpRequest()
        route = "/MAAS"
        query = "?op=signal"
        host = (
            node.boot_cluster_ip
            if ip_address(node.boot_cluster_ip).version == 4
            else f"[{node.boot_cluster_ip}]"
        )
        self.assertEqual(
            f"{request.scheme}://{host}:5248/MAAS?op=signal",
            build_metadata_url(
                request,
                route,
                node.get_boot_rack_controller(),
                node=node,
                extra=query,
            ),
        )

    def test_uses_rack_ipv4_enlist_without_external_dns(self):
        subnet = factory.make_Subnet(cidr="10.10.0.0/24", dns_servers=[])
        rack = factory.make_rack_with_interfaces(eth0=["10.10.0.2/24"])
        _enable_dhcp(subnet, rack)
        machine_ip = "10.10.0.100"
        self.assertEqual(
            "http://10-10-0-0--24.maas-internal:5248/MAAS",
            build_metadata_url(
                _make_request(machine_ip),
                "/MAAS",
                rack,
            ),
        )

    def test_uses_rack_ipv4_enlist_without_allow_dns(self):
        subnet = factory.make_Subnet(
            cidr="10.10.0.0/24", dns_servers=[], allow_dns=False
        )
        rack = factory.make_rack_with_interfaces(eth0=["10.10.0.2/24"])
        _enable_dhcp(subnet, rack)
        machine_ip = "10.10.0.100"
        assert "http://10.10.0.2:5248/MAAS" == build_metadata_url(
            _make_request(machine_ip), "/MAAS", rack
        )

    def test_uses_rack_ipv6_enlist_without_external_dns(self):
        subnet = factory.make_Subnet(
            cidr="fd12:3456:789a::/64", dns_servers=[]
        )
        rack = factory.make_rack_with_interfaces(eth0=["fd12:3456:789a::2/64"])
        _enable_dhcp(subnet, rack)
        machine_ip = "fd12:3456:789a::100"
        self.assertEqual(
            "http://fd12-3456-789a----64.maas-internal:5248/MAAS",
            build_metadata_url(
                _make_request(machine_ip),
                "/MAAS",
                rack,
            ),
        )

    def test_uses_rack_ipv4_enlist_if_external_dns(self):
        subnet = factory.make_Subnet(
            cidr="10.10.0.0/24", dns_servers=["10.10.0.1"]
        )
        rack = factory.make_rack_with_interfaces(eth0=["10.10.0.2/24"])
        _enable_dhcp(subnet, rack)
        machine_ip = "10.10.0.100"
        self.assertEqual(
            "http://10.10.0.2:5248/MAAS",
            build_metadata_url(
                _make_request(machine_ip),
                "/MAAS",
                rack,
            ),
        )

    def test_uses_rack_ipv6_if_external_dns(self):
        subnet = factory.make_Subnet(
            cidr="fd12:3456:789a::/64", dns_servers=["fd12:3456:789a::1"]
        )
        rack = factory.make_rack_with_interfaces(eth0=["fd12:3456:789a::2/64"])
        _enable_dhcp(subnet, rack)
        machine_ip = "fd12:3456:789a::100"
        self.assertEqual(
            "http://[fd12:3456:789a::2]:5248/MAAS",
            build_metadata_url(
                _make_request(machine_ip),
                "/MAAS",
                rack,
            ),
        )

    def test_uses_rack_enlist_relay_without_external_dns(self):
        # It's the DNS of the relayed subnet that is important.
        subnet1 = factory.make_Subnet(
            cidr="10.10.0.0/24", dns_servers=["10.10.0.1"]
        )
        subnet2 = factory.make_Subnet(cidr="10.20.0.0/24", dns_servers=[])
        rack = factory.make_rack_with_interfaces(eth0=["10.10.0.2/24"])
        _enable_dhcp(subnet2, rack, relay_vlan=subnet1.vlan)
        machine_ip = "10.20.0.100"
        self.assertEqual(
            "http://10-10-0-0--24.maas-internal:5248/MAAS",
            build_metadata_url(
                _make_request(machine_ip),
                "/MAAS",
                rack,
            ),
        )

    def test_uses_rack_enlist_relay_if_external_dns(self):
        # It's the DNS of the relayed subnet that is important.
        subnet1 = factory.make_Subnet(cidr="10.10.0.0/24", dns_servers=[])
        subnet2 = factory.make_Subnet(
            cidr="10.20.0.0/24", dns_servers=["10.20.0.1"]
        )
        rack = factory.make_rack_with_interfaces(eth0=["10.10.0.2/24"])
        _enable_dhcp(subnet2, rack, relay_vlan=subnet1.vlan)
        machine_ip = "10.20.0.100"
        self.assertEqual(
            "http://10.10.0.2:5248/MAAS",
            build_metadata_url(
                _make_request(machine_ip),
                "/MAAS",
                rack,
            ),
        )
