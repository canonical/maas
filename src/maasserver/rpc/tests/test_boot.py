# Copyright 2016-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
import datetime
from datetime import timedelta
import random
from unittest.mock import ANY, DEFAULT

from netaddr import IPAddress, IPNetwork
from testtools.matchers import ContainsAll, StartsWith

from maasserver import server_address
from maasserver.dns.config import get_resource_name_for_subnet
from maasserver.enum import (
    BOOT_RESOURCE_FILE_TYPE,
    BOOT_RESOURCE_TYPE,
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_STATUS,
    NODE_TYPE,
)
from maasserver.models import Config, Event
from maasserver.models.timestampedmodel import now
from maasserver.node_status import get_node_timeout, MONITORED_STATUSES
from maasserver.preseed import compose_enlistment_preseed_url
from maasserver.rpc import boot as boot_module
from maasserver.rpc.boot import (
    event_log_pxe_request,
    get_boot_config_for_machine,
    get_boot_filenames,
)
from maasserver.rpc.boot import (
    get_node_from_mac_or_hardware_uuid,
    merge_kparams_with_extra,
)
from maasserver.rpc.boot import get_config as orig_get_config
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.config import RegionConfigurationFixture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils import osystems
from maasserver.utils.orm import post_commit_hooks, reload_object
from maasserver.utils.osystems import get_release_from_distro_info
from maastesting.djangotestcase import count_queries
from maastesting.matchers import MockCalledOnceWith
from provisioningserver.events import EVENT_DETAILS, EVENT_TYPES
from provisioningserver.rpc.exceptions import BootConfigNoResponse
from provisioningserver.utils.network import get_source_address


def get_config(*args, query_count=42, **kwargs):
    count, result = count_queries(orig_get_config, *args, **kwargs)
    assert (
        count <= query_count
    ), f"Query count should be at most {query_count}, got {count}"
    return result


class TestKparamsMerge(MAASServerTestCase):
    def test_simple_merge(self):
        expected_state = "b=c a=b"
        calculated_state = merge_kparams_with_extra("a=b", "b=c")
        self.assertEqual(expected_state, calculated_state)

    def test_override_merge(self):
        expected_state = "b=d a=b"
        calculated_state = merge_kparams_with_extra("a=b b=c", "b=d")
        self.assertEqual(expected_state, calculated_state)

    def test_override_with_add_merge(self):
        expected_state = "b=d c=e a=b"
        calculated_state = merge_kparams_with_extra("a=b b=c", "b=d c=e")
        self.assertEqual(expected_state, calculated_state)


class TestGetConfig(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        self.region = factory.make_RegionController()
        self.useFixture(RegionConfigurationFixture())

    def tearDown(self):
        # None of tests depend on the post commit hooks, but they might
        # generate them. Remove them, since the MAASServerTestCase tear
        # down might complain that there are commit hooks.
        post_commit_hooks.reset()
        super().tearDown()

    def make_node(self, arch_name=None, **kwargs):
        architecture = make_usable_architecture(self, arch_name=arch_name)
        return factory.make_Node_with_Interface_on_Subnet(
            architecture="%s/generic" % architecture.split("/")[0], **kwargs
        )

    def make_node_with_extra(self, arch_name=None, extra=None, **kwargs):
        """
        Need since if we pass "extra" as part of kwargs, the code that creates
        a node will fail since "extra" isn't a valid parameter for that code
        path.

        :param arch_name:
        :param extra:
        :param kwargs:
        :return:
        """
        architecture = make_usable_architecture(
            self, arch_name=arch_name, extra=extra
        )
        return factory.make_Node_with_Interface_on_Subnet(
            architecture="%s/generic" % architecture.split("/")[0], **kwargs
        )

    def test_returns_all_kernel_parameters(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        make_usable_architecture(self)
        self.assertThat(
            get_config(rack_controller.system_id, local_ip, remote_ip),
            ContainsAll(
                [
                    "arch",
                    "subarch",
                    "osystem",
                    "release",
                    "kernel_osystem",
                    "kernel_release",
                    "kernel",
                    "initrd",
                    "boot_dtb",
                    "purpose",
                    "hostname",
                    "domain",
                    "preseed_url",
                    "fs_host",
                    "log_host",
                    "log_port",
                    "extra_opts",
                ]
            ),
        )

    def test_returns_success_for_known_node(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = self.make_node(status=NODE_STATUS.DEPLOYING)
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        # Should not raise BootConfigNoResponse.
        get_config(
            rack_controller.system_id,
            local_ip,
            remote_ip,
            mac=mac,
            hardware_uuid=node.hardware_uuid,
        )

    def test_gets_drivers_for_series(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = self.make_node(status=NODE_STATUS.DEPLOYING)
        mac = node.get_boot_interface().mac_address
        mock_get_third_party_driver = self.patch(
            boot_module, "get_third_party_driver"
        )
        Config.objects.set_config("default_distro_series", "focal")
        self.patch_autospec(boot_module, "event_log_pxe_request")
        get_config(
            rack_controller.system_id,
            local_ip,
            remote_ip,
            mac=mac,
            hardware_uuid=node.hardware_uuid,
        )
        mock_get_third_party_driver.assert_called_with(node, series="focal")

    def test_returns_success_for_known_node_mac(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = self.make_node(status=NODE_STATUS.DEPLOYING)
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        # Should not raise BootConfigNoResponse.
        get_config(rack_controller.system_id, local_ip, remote_ip, mac=mac)

    def test_returns_success_for_known_node_hardware_uuid(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = self.make_node(status=NODE_STATUS.DEPLOYING)
        self.patch_autospec(boot_module, "event_log_pxe_request")
        # Should not raise BootConfigNoResponse.
        get_config(
            rack_controller.system_id,
            local_ip,
            remote_ip,
            hardware_uuid=node.hardware_uuid,
        )

    def test_purpose_local_does_less_work(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = self.make_node_with_extra(
            status=NODE_STATUS.DEPLOYED, netboot=False
        )
        node.boot_cluster_ip = local_ip
        node.osystem = factory.make_name("osystem")
        node.distro_series = factory.make_name("distro_series")
        node.save()
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        config = get_config(
            rack_controller.system_id,
            local_ip,
            remote_ip,
            mac=mac,
            query_count=20,
        )
        self.assertEqual(
            {
                "system_id": node.system_id,
                "arch": node.split_arch()[0],
                "subarch": node.split_arch()[1],
                "osystem": node.osystem,
                "release": node.distro_series,
                "kernel_osystem": node.osystem,
                "kernel_release": node.distro_series,
                "kernel": "",
                "initrd": "",
                "boot_dtb": "",
                "purpose": "local",
                "hostname": node.hostname,
                "domain": node.domain.name,
                "preseed_url": ANY,
                "fs_host": local_ip,
                "log_host": local_ip,
                "log_port": 5247,
                "extra_opts": "",
                "http_boot": True,
                "ephemeral_opts": "",
            },
            config,
        )

    def test_purpose_local_uses_maas_syslog_port(self):
        syslog_port = factory.pick_port()
        Config.objects.set_config("maas_syslog_port", syslog_port)
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = self.make_node_with_extra(
            status=NODE_STATUS.DEPLOYED, netboot=False
        )
        node.boot_cluster_ip = local_ip
        node.osystem = factory.make_name("osystem")
        node.distro_series = factory.make_name("distro_series")
        node.save()
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        config = get_config(
            rack_controller.system_id,
            local_ip,
            remote_ip,
            mac=mac,
            query_count=20,
        )
        self.assertEqual(
            {
                "system_id": node.system_id,
                "arch": node.split_arch()[0],
                "subarch": node.split_arch()[1],
                "osystem": node.osystem,
                "release": node.distro_series,
                "kernel_osystem": node.osystem,
                "kernel_release": node.distro_series,
                "kernel": "",
                "initrd": "",
                "boot_dtb": "",
                "purpose": "local",
                "hostname": node.hostname,
                "domain": node.domain.name,
                "preseed_url": ANY,
                "fs_host": local_ip,
                "log_host": local_ip,
                "log_port": syslog_port,
                "extra_opts": "",
                "http_boot": True,
                "ephemeral_opts": "",
            },
            config,
        )

    def test_changes_purpose_to_local_device_for_device(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        device = self.make_node_with_extra(
            status=NODE_STATUS.DEPLOYED,
            netboot=False,
            node_type=NODE_TYPE.DEVICE,
        )
        device.boot_cluster_ip = local_ip
        device.save()
        mac = device.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        maaslog = self.patch(boot_module, "maaslog")
        config = get_config(
            rack_controller.system_id,
            local_ip,
            remote_ip,
            mac=mac,
            query_count=14,
        )
        self.assertEqual(
            {
                "system_id": device.system_id,
                "arch": device.split_arch()[0],
                "subarch": device.split_arch()[1],
                "osystem": "",
                "release": "",
                "kernel_osystem": "",
                "kernel_release": "",
                "kernel": "",
                "initrd": "",
                "boot_dtb": "",
                "purpose": "local-device",
                "hostname": device.hostname,
                "domain": device.domain.name,
                "preseed_url": ANY,
                "fs_host": local_ip,
                "log_host": local_ip,
                "log_port": 5247,
                "extra_opts": "",
                "http_boot": True,
                "ephemeral_opts": "",
            },
            config,
        )
        self.assertThat(
            maaslog.warning,
            MockCalledOnceWith(
                "Device %s with MAC address %s is PXE booting; "
                "instructing the device to boot locally."
                % (device.hostname, mac)
            ),
        )

    def test_purpose_local_to_xinstall_for_ephemeral_deployment(self):
        # A diskless node is one that it is ephemerally deployed.
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = self.make_node_with_extra(
            status=NODE_STATUS.DEPLOYED, netboot=False, ephemeral_deploy=True
        )
        node.boot_cluster_ip = local_ip
        node.osystem = factory.make_name("osystem")
        node.distro_series = factory.make_name("distro_series")
        node.save()
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac
        )
        self.assertEqual(config["purpose"], "xinstall")

    def test_custom_ephemeral_deployment(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = self.make_node_with_extra(
            status=NODE_STATUS.DEPLOYED, netboot=False, ephemeral_deploy=True
        )
        node.boot_cluster_ip = local_ip
        node.osystem = "centos"
        node.distro_series = "8"
        node.architecture = "amd64/generic"
        node.save()
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac
        )
        self.assertEqual(config["osystem"], "centos")
        self.assertEqual(config["release"], "8")
        self.assertEqual(config["arch"], "amd64")
        self.assertEqual(config["subarch"], "generic")
        self.assertEqual(
            config["kernel_osystem"],
            Config.objects.get_config(name="commissioning_osystem"),
        )
        self.assertEqual(
            config["kernel_release"],
            Config.objects.get_config(name="commissioning_distro_series"),
        )
        self.assertEqual(config["purpose"], "xinstall")

    # See https://github.com/canonical/cloud-init/issues/4418 for more details
    def test_preseed_url_not_using_domain_names_for_custom_ephemeral_deployments(
        self,
    ):
        network = factory.make_ipv4_network()
        subnet = factory.make_Subnet(
            cidr=str(network.cidr), dhcp_on=True, dns_servers=[]
        )
        rack_controller = factory.make_RackController(subnet=subnet)
        local_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            subnet=subnet,
        ).ip
        remote_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            subnet=subnet,
        ).ip
        node = self.make_node_with_extra(
            subnet=subnet,
            status=NODE_STATUS.DEPLOYED,
            netboot=False,
            ephemeral_deploy=True,
        )
        node.boot_cluster_ip = local_ip
        node.osystem = "centos"
        node.distro_series = "8"
        node.architecture = "amd64/generic"
        node.save()
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac
        )
        assert ".maas-internal:5248" not in config["preseed_url"]
        assert local_ip in config["preseed_url"]

    def test_returns_kparams_for_known_node(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()

        """
        The make_node function will result in a boot resource being created
        with an architecture that looks like "arch-YYY/hwe-Z", with YYY being
        a random string and Z being the first letter of the default
        commissioning image. If we don't create a node with this same kernel
        name, the node will use an architecture name of arch-YYY/generic which
        means the get_config won't find the matching boot resource file with
        the kparams attribute.
        """
        default_series = Config.objects.get_config(
            name="commissioning_distro_series"
        )
        release = get_release_from_distro_info(default_series)
        hwe_kernel = "hwe-%s" % (release["version"].split()[0])

        node = self.make_node_with_extra(
            status=NODE_STATUS.DEPLOYING,
            extra={"kparams": "a=b"},
            hwe_kernel=hwe_kernel,
        )

        """
        Create a tag so that we can make sure the kparams attribute got merged
        with the tag's kernel_opts attribute.
        """
        tag = factory.make_Tag(kernel_opts="b=c")
        node.tags.add(tag)

        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac
        )
        extra = config.get("extra_opts", None)

        self.assertIn("b=c", extra)
        self.assertIn("a=b", extra)

    def test_raises_BootConfigNoResponse_for_unknown_node(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        mac = factory.make_mac_address(delimiter="-")
        hardware_uuid = factory.make_UUID()
        self.assertRaises(
            BootConfigNoResponse,
            get_config,
            rack_controller.system_id,
            local_ip,
            remote_ip,
            mac=mac,
            hardware_uuid=hardware_uuid,
        )

    def test_returns_success_for_detailed_but_unknown_node(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        architecture = make_usable_architecture(self)
        arch = architecture.split("/")[0]
        factory.make_default_ubuntu_release_bootable(arch)
        mac = factory.make_mac_address(delimiter="-")
        self.patch_autospec(boot_module, "event_log_pxe_request")
        # Should not raise BootConfigNoResponse.
        get_config(
            rack_controller.system_id,
            local_ip,
            remote_ip,
            arch=arch,
            subarch="generic",
            mac=mac,
        )

    def test_returns_global_kernel_params_for_enlisting_node(self):
        # An 'enlisting' node means it looks like a node with details but we
        # don't know about it yet.  It should still receive the global
        # kernel options.
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        value = factory.make_string()
        Config.objects.set_config("kernel_opts", value)
        architecture = make_usable_architecture(self)
        arch = architecture.split("/")[0]
        factory.make_default_ubuntu_release_bootable(arch)
        mac = factory.make_mac_address(delimiter="-")
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id,
            local_ip,
            remote_ip,
            arch=arch,
            subarch="generic",
            mac=mac,
        )
        self.assertEqual(value, observed_config["extra_opts"])

    def test_uses_present_boot_image(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        factory.make_default_ubuntu_release_bootable("amd64")
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip
        )
        self.assertEqual("amd64", observed_config["arch"])

    def test_defaults_to_i386_for_default(self):
        # As a lowest-common-denominator, i386 is chosen when the node is not
        # yet known to MAAS.
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        expected_arch = tuple(
            make_usable_architecture(
                self, arch_name="i386", subarch_name="hwe-20.04"
            ).split("/")
        )
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip
        )
        observed_arch = observed_config["arch"], observed_config["subarch"]
        self.assertEqual(expected_arch, observed_arch)

    def test_uses_fixed_hostname_for_enlisting_node(self):
        rack_controller = factory.make_RackController()
        # factory.make_default_ubuntu_release_bootable()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        make_usable_architecture(self)
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip
        )
        self.assertEqual("maas-enlist", observed_config.get("hostname"))

    def test_uses_local_domain_for_enlisting_node(self):
        rack_controller = factory.make_RackController()
        # factory.make_default_ubuntu_release_bootable()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        make_usable_architecture(self)
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip
        )
        self.assertEqual("local", observed_config.get("domain"))

    def test_splits_domain_from_node_hostname(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        host = factory.make_name("host")
        domainname = factory.make_name("domain")
        domain = factory.make_Domain(name=domainname)
        full_hostname = ".".join([host, domainname])
        node = self.make_node(hostname=full_hostname, domain=domain)
        interface = node.get_boot_interface()
        mac = interface.mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac
        )
        self.assertEqual(host, observed_config.get("hostname"))
        self.assertEqual(domainname, observed_config.get("domain"))

    def test_has_enlistment_preseed_url_with_local_ip_no_subnet_ipv4(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address(ipv6=False)
        remote_ip = factory.make_ip_address(ipv6=False)
        factory.make_default_ubuntu_release_bootable()
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip
        )
        self.assertEqual(
            compose_enlistment_preseed_url(
                base_url="http://%s:5248/" % local_ip
            ),
            observed_config["preseed_url"],
        )

    def test_has_enlistment_preseed_url_with_local_ip_no_subnet_ipv6(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address(ipv6=True)
        remote_ip = factory.make_ip_address(ipv6=True)
        factory.make_default_ubuntu_release_bootable()
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip
        )
        assert (
            compose_enlistment_preseed_url(
                base_url="http://[%s]:5248/" % local_ip
            )
            == observed_config["preseed_url"]
        )

    def test_has_enlistment_preseed_url_with_local_ip_subnet_with_dns(self):
        rack_controller = factory.make_RackController()
        subnet = factory.make_Subnet()
        local_ip = factory.pick_ip_in_Subnet(subnet)
        remote_ip = factory.make_ip_address()
        factory.make_default_ubuntu_release_bootable()
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip
        )
        base_url = (
            "http://[%s]:5248/" % local_ip
            if IPAddress(local_ip).version == 6
            else "http://%s:5248/" % local_ip
        )
        assert (
            compose_enlistment_preseed_url(base_url=base_url)
            == observed_config["preseed_url"]
        )

    def test_has_enlistment_preseed_url_internal_domain(self):
        rack_controller = factory.make_RackController()
        vlan = factory.make_VLAN(dhcp_on=True, primary_rack=rack_controller)
        subnet = factory.make_Subnet(vlan=vlan)
        subnet.dns_servers = []
        subnet.save()
        local_ip = factory.pick_ip_in_Subnet(subnet)
        remote_ip = factory.make_ip_address()
        factory.make_default_ubuntu_release_bootable()
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip
        )
        self.assertEqual(
            compose_enlistment_preseed_url(
                base_url="http://%s.%s:5248/"
                % (
                    get_resource_name_for_subnet(subnet),
                    Config.objects.get_config("maas_internal_domain"),
                )
            ),
            observed_config["preseed_url"],
        )

    def test_has_enlistment_preseed_url_with_region_ip(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        factory.make_default_ubuntu_release_bootable()
        Config.objects.set_config("use_rack_proxy", False)
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip
        )
        self.assertEqual(
            compose_enlistment_preseed_url(
                default_region_ip=get_source_address(remote_ip)
            ),
            observed_config["preseed_url"],
        )

    def test_enlistment_checks_default_min_hwe_kernel(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        arch = "armhf"
        Config.objects.set_config("default_min_hwe_kernel", "hwe-x")
        self.patch(boot_module, "get_boot_filenames").return_value = (
            None,
            None,
            None,
        )
        factory.make_default_ubuntu_release_bootable(arch)
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, arch=arch
        )
        self.assertEqual("hwe-20.04", observed_config["subarch"])

    def test_enlistment_return_generic_when_none(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        arch = "armhf"
        self.patch(boot_module, "get_boot_filenames").return_value = (
            None,
            None,
            None,
        )
        self.patch(boot_module, "get_working_kernel").return_value = None
        factory.make_default_ubuntu_release_bootable(arch)
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, arch=arch
        )
        self.assertEqual("generic", observed_config["subarch"])

    def test_preseed_url_for_known_node_local_ip_no_subnet(self):
        rack_url = "http://%s" % factory.make_name("host")
        network = IPNetwork("10.1.1/24")
        local_ip = factory.pick_ip_in_network(network)
        remote_ip = factory.make_ip_address()
        self.patch(server_address, "resolve_hostname").return_value = {
            local_ip
        }
        rack_controller = factory.make_RackController(url=rack_url)
        node = self.make_node(primary_rack=rack_controller)
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac
        )
        base_url = (
            "http://[%s]:5248/" % local_ip
            if IPAddress(local_ip).version == 6
            else "http://%s:5248/" % local_ip
        )
        assert observed_config["preseed_url"].startswith(base_url)

    def test_preseed_url_for_known_node_local_ip_subnet_with_dns(self):
        rack_url = "http://%s" % factory.make_name("host")
        subnet = factory.make_Subnet()
        local_ip = factory.pick_ip_in_Subnet(subnet)
        remote_ip = factory.make_ip_address()
        self.patch(server_address, "resolve_hostname").return_value = {
            local_ip
        }
        rack_controller = factory.make_RackController(url=rack_url)
        node = self.make_node(primary_rack=rack_controller)
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac
        )
        base_url = (
            "http://[%s]:5248/" % local_ip
            if IPAddress(local_ip).version == 6
            else "http://%s:5248/" % local_ip
        )
        assert observed_config["preseed_url"].startswith(base_url)

    def test_preseed_url_for_known_node_internal_domain(self):
        rack_url = "http://%s" % factory.make_name("host")
        rack_controller = factory.make_RackController(url=rack_url)
        vlan = factory.make_VLAN(dhcp_on=True, primary_rack=rack_controller)
        subnet = factory.make_Subnet(vlan=vlan)
        subnet.dns_servers = []
        subnet.save()
        local_ip = factory.pick_ip_in_Subnet(subnet)
        remote_ip = factory.make_ip_address()
        self.patch(server_address, "resolve_hostname").return_value = {
            local_ip
        }
        node = self.make_node(primary_rack=rack_controller)
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac
        )
        self.assertThat(
            observed_config["preseed_url"],
            StartsWith(
                "http://%s.%s:5248"
                % (
                    get_resource_name_for_subnet(subnet),
                    Config.objects.get_config("maas_internal_domain"),
                )
            ),
        )

    def test_preseed_url_for_known_node_uses_rack_url(self):
        rack_url = "http://%s" % factory.make_name("host")
        network = IPNetwork("10.1.1/24")
        local_ip = factory.pick_ip_in_network(network)
        remote_ip = factory.make_ip_address()
        self.patch(server_address, "resolve_hostname").return_value = {
            local_ip
        }
        rack_controller = factory.make_RackController(url=rack_url)
        node = self.make_node(primary_rack=rack_controller)
        mac = node.get_boot_interface().mac_address
        Config.objects.set_config("use_rack_proxy", False)
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac
        )
        self.assertThat(observed_config["preseed_url"], StartsWith(rack_url))

    def test_uses_boot_purpose_enlistment(self):
        # test that purpose is set to "commissioning" for
        # enlistment (when node is None).
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        arch = "armhf"
        make_usable_architecture(self, arch_name=arch)
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, arch=arch
        )
        self.assertEqual("commissioning", observed_config["purpose"])

    def test_returns_enlist_config_if_no_architecture_provided(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        make_usable_architecture(self, arch_name=boot_module.DEFAULT_ARCH)
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip
        )
        self.assertEqual("enlist", observed_config["purpose"])

    def test_returns_fs_host_as_cluster_controller(self):
        # The kernel parameter `fs_host` points to the cluster controller
        # address, which is passed over within the `local_ip` parameter.
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        make_usable_architecture(self)
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip
        )
        self.assertEqual(local_ip, observed_config["fs_host"])

    def test_returns_extra_kernel_options(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        extra_kernel_opts = factory.make_string()
        Config.objects.set_config("kernel_opts", extra_kernel_opts)
        make_usable_architecture(self)
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip
        )
        self.assertEqual(extra_kernel_opts, observed_config["extra_opts"])

    def test_returns_empty_string_for_no_extra_kernel_opts(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        make_usable_architecture(self)
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip
        )
        self.assertEqual("", observed_config["extra_opts"])

    def test_returns_commissioning_for_insane_state(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = self.make_node(status=NODE_STATUS.BROKEN)
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac
        )
        # The 'purpose' of the PXE config is 'commissioning' here
        # even if the 'purpose' returned by node.get_boot_purpose
        # is 'poweroff' because MAAS needs to bring the machine
        # up in a commissioning environment in order to power
        # the machine down.
        self.assertEqual("commissioning", observed_config["purpose"])

    def test_returns_commissioning_for_ready_node(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = self.make_node(status=NODE_STATUS.READY)
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac
        )
        self.assertEqual("commissioning", observed_config["purpose"])

    def test_uses_rescue_mode_boot_purpose(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = self.make_node(status=NODE_STATUS.ENTERING_RESCUE_MODE)
        mac = node.get_boot_interface().mac_address
        event_log_pxe_request = self.patch_autospec(
            boot_module, "event_log_pxe_request"
        )
        get_config(rack_controller.system_id, local_ip, remote_ip, mac=mac)
        self.assertThat(
            event_log_pxe_request, MockCalledOnceWith(node, "rescue")
        )

    def test_uses_rescue_mode_reboot_purpose(self):
        # Regression test for LP:1749210
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = self.make_node(status=NODE_STATUS.RESCUE_MODE)
        mac = node.get_boot_interface().mac_address
        event_log_pxe_request = self.patch_autospec(
            boot_module, "event_log_pxe_request"
        )
        get_config(rack_controller.system_id, local_ip, remote_ip, mac=mac)
        self.assertThat(
            event_log_pxe_request, MockCalledOnceWith(node, "rescue")
        )

    def test_calls_event_log_pxe_request(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = self.make_node()
        mac = node.get_boot_interface().mac_address
        event_log_pxe_request = self.patch_autospec(
            boot_module, "event_log_pxe_request"
        )
        get_config(rack_controller.system_id, local_ip, remote_ip, mac=mac)
        self.assertThat(
            event_log_pxe_request,
            MockCalledOnceWith(node, node.get_boot_purpose()),
        )

    def test_event_log_pxe_request_for_known_boot_purpose(self):
        purposes = [
            ("commissioning", "commissioning"),
            ("rescue", "rescue mode"),
            ("xinstall", "installation"),
            ("local", "local boot"),
            ("poweroff", "power off"),
        ]
        for purpose, description in purposes:
            node = self.make_node()
            event_log_pxe_request(node, purpose)
            events = Event.objects.filter(node=node).order_by("id")
            self.assertEqual(description, events[0].description)
            self.assertEqual(
                events[1].type.description,
                EVENT_DETAILS[EVENT_TYPES.PERFORMING_PXE_BOOT].description,
            )

    def test_sets_boot_interface_when_empty(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = self.make_node()
        nic = node.get_boot_interface()
        node.boot_interface = None
        node.save()
        mac = nic.mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        get_config(rack_controller.system_id, local_ip, remote_ip, mac=mac)
        self.assertEqual(nic, reload_object(node).boot_interface)

    def test_sets_boot_interface_handles_virtual_nics_same_mac(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = self.make_node()
        nic = node.get_boot_interface()
        # Create a bridge that has the same mac address as the parent nic.
        factory.make_Interface(
            INTERFACE_TYPE.BRIDGE, parents=[nic], mac_address=nic.mac_address
        )
        node.boot_interface = None
        node.save()
        mac = nic.mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        get_config(rack_controller.system_id, local_ip, remote_ip, mac=mac)
        self.assertEqual(nic, reload_object(node).boot_interface)

    def test_updates_boot_interface_when_changed(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = self.make_node()
        node.boot_interface = node.get_boot_interface()
        node.save()
        nic = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=node.boot_interface.vlan
        )
        mac = nic.mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        get_config(rack_controller.system_id, local_ip, remote_ip, mac=mac)
        self.assertEqual(nic, reload_object(node).boot_interface)

    def test_sets_boot_interface_when_given_hardware_uuid(self):
        node = self.make_node()
        nic = node.get_boot_interface()
        node.boot_interface = None
        node.save()
        rack_controller = nic.vlan.primary_rack
        subnet = nic.vlan.subnet_set.first()
        local_ip = factory.pick_ip_in_Subnet(subnet)
        self.patch_autospec(boot_module, "event_log_pxe_request")
        get_config(
            rack_controller.system_id,
            local_ip,
            factory.make_ip_address(),
            hardware_uuid=node.hardware_uuid,
        )
        self.assertEqual(nic, reload_object(node).boot_interface)

    def test_sets_boot_interface_hardware_uuid_different_vlan(self):
        node = self.make_node()
        vlan2 = factory.make_VLAN(
            dhcp_on=True, primary_rack=factory.make_RackController()
        )
        nic2 = factory.make_Interface(node=node, vlan=vlan2)
        subnet = factory.make_Subnet(vlan=nic2.vlan)
        rack_controller = nic2.vlan.primary_rack

        local_ip = factory.pick_ip_in_Subnet(subnet)
        self.patch_autospec(boot_module, "event_log_pxe_request")
        get_config(
            rack_controller.system_id,
            local_ip,
            factory.make_ip_address(),
            hardware_uuid=node.hardware_uuid,
        )
        self.assertEqual(nic2, reload_object(node).boot_interface)

    def test_no_sets_boot_interface_hardware_uuid_same_vlan(self):
        node = self.make_node()
        nic1 = node.boot_interface
        nic2 = factory.make_Interface(node=node, vlan=node.boot_interface.vlan)
        rack_controller = nic1.vlan.primary_rack

        subnet = nic1.vlan.subnet_set.first()
        local_ip = factory.pick_ip_in_Subnet(subnet)
        self.patch_autospec(boot_module, "event_log_pxe_request")
        get_config(
            rack_controller.system_id,
            local_ip,
            factory.make_ip_address(),
            hardware_uuid=node.hardware_uuid,
        )
        self.assertEqual(nic1, reload_object(node).boot_interface)
        node.boot_interface = nic2
        node.save()
        get_config(
            rack_controller.system_id,
            local_ip,
            factory.make_ip_address(),
            hardware_uuid=node.hardware_uuid,
        )
        self.assertEqual(nic2, reload_object(node).boot_interface)

    def test_sets_boot_cluster_ip_when_empty(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = self.make_node()
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        get_config(rack_controller.system_id, local_ip, remote_ip, mac=mac)
        self.assertEqual(local_ip, reload_object(node).boot_cluster_ip)

    def test_updates_boot_cluster_ip_when_changed(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = self.make_node()
        node.boot_cluster_ip = factory.make_ipv4_address()
        node.save()
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        get_config(rack_controller.system_id, local_ip, remote_ip, mac=mac)
        self.assertEqual(local_ip, reload_object(node).boot_cluster_ip)

    def test_updates_bios_boot_method(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = self.make_node()
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        get_config(
            rack_controller.system_id,
            local_ip,
            remote_ip,
            mac=mac,
            bios_boot_method="pxe",
        )
        self.assertEqual("pxe", reload_object(node).bios_boot_method)

    def test_resets_status_expires(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        status = random.choice(MONITORED_STATUSES)
        node = self.make_node(
            status=status, status_expires=factory.make_date()
        )
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        get_config(rack_controller.system_id, local_ip, remote_ip, mac=mac)
        node = reload_object(node)
        # Testing for the exact time will fail during testing due to now()
        # being different in reset_status_expires vs here. Pad by 1 minute
        # to make sure its reset but won't fail testing.
        expected_time = now() + timedelta(minutes=get_node_timeout(status))
        self.assertGreaterEqual(
            node.status_expires, expected_time - timedelta(minutes=1)
        )
        self.assertLessEqual(
            node.status_expires, expected_time + timedelta(minutes=1)
        )

    def test_sets_boot_interface_vlan_to_match_rack_controller(self):
        rack_controller = factory.make_RackController()
        rack_fabric = factory.make_Fabric()
        rack_vlan = rack_fabric.get_default_vlan()
        rack_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=rack_vlan
        )
        rack_subnet = factory.make_Subnet(vlan=rack_vlan)
        rack_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=rack_subnet,
            interface=rack_interface,
        )
        remote_ip = factory.make_ip_address()
        node = self.make_node()
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        get_config(rack_controller.system_id, rack_ip.ip, remote_ip, mac=mac)
        self.assertEqual(
            rack_vlan, reload_object(node).get_boot_interface().vlan
        )

    def test_doesnt_change_boot_interface_vlan_when_using_dhcp_relay(self):
        rack_controller = factory.make_RackController()
        rack_fabric = factory.make_Fabric()
        rack_vlan = rack_fabric.get_default_vlan()
        rack_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=rack_vlan
        )
        rack_subnet = factory.make_Subnet(vlan=rack_vlan)
        rack_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=rack_subnet,
            interface=rack_interface,
        )
        relay_vlan = factory.make_VLAN(relay_vlan=rack_vlan)
        remote_ip = factory.make_ip_address()
        node = self.make_node(vlan=relay_vlan)
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        get_config(rack_controller.system_id, rack_ip.ip, remote_ip, mac=mac)
        self.assertEqual(
            relay_vlan, reload_object(node).get_boot_interface().vlan
        )

    def test_changes_boot_interface_vlan_not_relayed_through_rack(self):
        rack_controller = factory.make_RackController()
        rack_fabric = factory.make_Fabric()
        rack_vlan = rack_fabric.get_default_vlan()
        rack_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack_controller, vlan=rack_vlan
        )
        rack_subnet = factory.make_Subnet(vlan=rack_vlan)
        rack_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=rack_subnet,
            interface=rack_interface,
        )
        other_vlan = factory.make_VLAN()
        relay_vlan = factory.make_VLAN(relay_vlan=other_vlan)
        remote_ip = factory.make_ip_address()
        node = self.make_node(vlan=relay_vlan)
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        get_config(rack_controller.system_id, rack_ip.ip, remote_ip, mac=mac)
        self.assertEqual(
            rack_vlan, reload_object(node).get_boot_interface().vlan
        )

    def test_returns_commissioning_os_series_for_other_oses(self):
        osystem = Config.objects.get_config("default_osystem")
        release = Config.objects.get_config("default_distro_series")
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        self.make_node(arch_name="amd64")
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.DEPLOYING,
            osystem="centos",
            distro_series="centos71",
            architecture="amd64/generic",
            primary_rack=rack_controller,
        )
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac
        )
        self.assertEqual(osystem, observed_config["osystem"])
        self.assertEqual(release, observed_config["release"])

    def test_query_commissioning_os_series_for_other_oses(self):
        osystem = Config.objects.get_config("default_osystem")
        release = Config.objects.get_config("default_distro_series")
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        self.make_node(arch_name="amd64")
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.DEPLOYING,
            osystem="centos",
            distro_series="centos71",
            architecture="amd64/generic",
            primary_rack=rack_controller,
        )
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac
        )
        self.assertEqual(osystem, observed_config["osystem"])
        self.assertEqual(release, observed_config["release"])

    def test_commissioning_node_uses_min_hwe_kernel(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.COMMISSIONING, min_hwe_kernel="hwe-20.04"
        )
        arch = node.split_arch()[0]
        factory.make_default_ubuntu_release_bootable(arch)
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac
        )
        self.assertEqual("hwe-20.04", observed_config["subarch"])

    def test_commissioning_node_uses_min_hwe_kernel_converted(self):
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = self.make_node(
            status=NODE_STATUS.COMMISSIONING, min_hwe_kernel="hwe-x"
        )
        make_usable_architecture(self)
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac
        )
        self.assertEqual("hwe-20.04", observed_config["subarch"])

    def test_commissioning_node_uses_min_hwe_kernel_reports_missing(self):
        factory.make_BootSourceCache(
            release="20.10",
            subarch="hwe-20.10",
            release_title="20.10 Groovy Gorilla",
            release_codename="Groovy Gorilla",
        )
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = self.make_node(
            status=NODE_STATUS.COMMISSIONING, min_hwe_kernel="hwe-20.10"
        )
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac
        )
        self.assertEqual("no-such-kernel", observed_config["subarch"])

    # LP: #1768321 - Test to ensure commissioning os/kernel is used for
    # hardware testing on deployed machines.
    def test_testing_deployed_node_uses_none_default_min_hwe_kernel(self):
        self.patch(boot_module, "get_boot_filenames").return_value = (
            None,
            None,
            None,
        )
        commissioning_series = "bionic"
        commissioning_subarch = "ga-18.04"
        Config.objects.set_config(
            "commissioning_distro_series", commissioning_series
        )
        distro_series = "xenial"
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = self.make_node(
            status=NODE_STATUS.TESTING,
            previous_status=NODE_STATUS.DEPLOYED,
            osystem="ubuntu",
            distro_series="xenial",
            arch_name="amd64",
            primary_rack=rack_controller,
        )
        arch, platform = node.split_arch()
        factory.make_usable_boot_resource(
            name=f"ubuntu/{commissioning_series}",
            architecture=f"{arch}/{commissioning_subarch}",
            supported_platforms=f"generic,{platform}",
        )
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac
        )
        self.assertEqual(commissioning_series, observed_config["release"])
        self.assertEqual(commissioning_subarch, observed_config["subarch"])
        self.assertEqual(node.distro_series, distro_series)

    # LP: #1768321 - Test to ensure commissioning os/kernel is used for
    # hardware testing on deployed machines.
    def test_testing_deployed_node_uses_default_min_hwe_kernel(self):
        self.patch(boot_module, "get_boot_filenames").return_value = (
            None,
            None,
            None,
        )
        commissioning_series = "bionic"
        default_min_hwe_kernel = "ga-18.04"
        Config.objects.set_config(
            "commissioning_distro_series", commissioning_series
        )
        Config.objects.set_config(
            "default_min_hwe_kernel", default_min_hwe_kernel
        )
        distro_series = "xenial"
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = self.make_node(
            status=NODE_STATUS.TESTING,
            previous_status=NODE_STATUS.DEPLOYED,
            osystem="ubuntu",
            distro_series="xenial",
            arch_name="amd64",
            primary_rack=rack_controller,
        )
        arch, platform = node.split_arch()
        factory.make_usable_boot_resource(
            name=f"ubuntu/{commissioning_series}",
            architecture=f"{arch}/{default_min_hwe_kernel}",
            supported_platforms=f"generic,{platform}",
        )
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac
        )
        self.assertEqual(commissioning_series, observed_config["release"])
        self.assertEqual(default_min_hwe_kernel, observed_config["subarch"])
        self.assertEqual(distro_series, node.distro_series)

    def test_commissioning_node_uses_machine_hwe_kernel(self):
        # Regression test for LP: #1768321 and LP: #1730525, see comment
        # in boot.py
        subarch = "ga-90.90"
        mock_version = {
            "version": "90.90",
            "codename": "Miraculous Mockingbird",
            "series": "miraculous",
            "created": datetime.date(2090, 3, 5),
            "release": datetime.date(2090, 10, 20),
            "eol": datetime.date(2100, 4, 30),
            "eol_lts": None,
            "eol_elts": None,
            "eol_esm": None,
            "eol_server": None,
        }
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = self.make_node(
            status=NODE_STATUS.DISK_ERASING, hwe_kernel=subarch
        )
        arch, platform = node.split_arch()
        factory.make_usable_boot_resource(
            name="ubuntu/focal",
            architecture=f"{arch}/{subarch}",
            supported_platforms=f"generic,{platform}",
        )

        self.patch(osystems, "get_release_from_distro_info").side_effect = (
            lambda s: mock_version if s == subarch else DEFAULT
        )

        make_usable_architecture(self)
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac
        )
        self.assertEqual(subarch, observed_config["subarch"])

    def test_returns_ubuntu_os_series_for_ubuntu_xinstall(self):
        self.patch(boot_module, "get_boot_filenames").return_value = (
            None,
            None,
            None,
        )
        distro_series = random.choice(["trusty", "vivid", "wily", "xenial"])
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = self.make_node(
            status=NODE_STATUS.DEPLOYING,
            osystem="ubuntu",
            distro_series=distro_series,
            primary_rack=rack_controller,
        )
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac
        )
        self.assertEqual(distro_series, observed_config["release"])
        self.assertEqual("", observed_config["ephemeral_opts"])

    def test_returns_base_image_for_custom_ubuntu_image_xinstall(self):
        self.patch(boot_module, "get_boot_filenames").return_value = (
            None,
            None,
            None,
        )
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        image_name = factory.make_name("custom-image")
        base_image_series = random.choice(
            ["trusty", "vivid", "wily", "xenial"]
        )
        custom_image = factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
            name=image_name,
            kflavor="generic",
            base_image="ubuntu/%s" % base_image_series,
        )
        node = self.make_node(
            status=NODE_STATUS.DEPLOYING,
            osystem="custom",
            distro_series=image_name,
            primary_rack=rack_controller,
        )
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac
        )
        expected_osystem, expected_series = custom_image.base_image.split("/")
        self.assertEqual(expected_osystem, observed_config["osystem"])
        self.assertEqual(expected_series, observed_config["release"])
        self.assertEqual("", observed_config["ephemeral_opts"])

    def test_returns_quirks_for_centos_image_xinstall(self):
        osystem = Config.objects.get_config("default_osystem")
        release = Config.objects.get_config("default_distro_series")
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        self.make_node(arch_name="amd64")
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.DEPLOYING,
            osystem="centos",
            distro_series="centos71",
            architecture="amd64/generic",
            primary_rack=rack_controller,
        )
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac
        )
        self.assertEqual(osystem, observed_config["osystem"])
        self.assertEqual(release, observed_config["release"])
        self.assertEqual(
            "nvme-core.multipath=0", observed_config["ephemeral_opts"]
        )

    # XXX: roaksoax LP: #1739761 - Deploying precise is now done using
    # the commissioning ephemeral environment.
    def test_returns_commissioning_os_series_for_precise_xinstall(self):
        self.patch(boot_module, "get_boot_filenames").return_value = (
            None,
            None,
            None,
        )
        commissioning_series = "xenial"
        Config.objects.set_config(
            "commissioning_distro_series", commissioning_series
        )
        distro_series = "precise"
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = self.make_node(
            status=NODE_STATUS.DEPLOYING,
            osystem="ubuntu",
            distro_series=distro_series,
            primary_rack=rack_controller,
        )
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac
        )
        self.assertEqual(commissioning_series, observed_config["release"])
        self.assertEqual(distro_series, node.distro_series)

    def test_returns_commissioning_os_when_erasing_disks(self):
        self.patch(boot_module, "get_boot_filenames").return_value = (
            None,
            None,
            None,
        )
        commissioning_osystem = factory.make_name("os")
        Config.objects.set_config(
            "commissioning_osystem", commissioning_osystem
        )
        commissioning_series = factory.make_name("series")
        Config.objects.set_config(
            "commissioning_distro_series", commissioning_series
        )
        rack_controller = factory.make_RackController()
        local_ip = factory.make_ip_address()
        remote_ip = factory.make_ip_address()
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.DISK_ERASING,
            osystem=factory.make_name("centos"),
            distro_series=factory.make_name("release"),
            primary_rack=rack_controller,
        )
        mac = node.get_boot_interface().mac_address
        self.patch_autospec(boot_module, "event_log_pxe_request")
        observed_config = get_config(
            rack_controller.system_id, local_ip, remote_ip, mac=mac
        )
        self.assertEqual(commissioning_osystem, observed_config["osystem"])
        self.assertEqual(commissioning_series, observed_config["release"])


class TestGetBootFilenames(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        self.region = factory.make_RegionController()

    def test_get_filenames(self):
        release = factory.make_default_ubuntu_release_bootable()
        arch, subarch = release.architecture.split("/")
        osystem, series = release.name.split("/")
        boot_resource_set = release.get_latest_complete_set()
        factory.make_boot_resource_file_with_content(
            boot_resource_set,
            filetype=BOOT_RESOURCE_FILE_TYPE.BOOT_DTB,
            synced=[(self.region, -1)],
        )

        kernel, initrd, boot_dbt = get_boot_filenames(
            arch, subarch, osystem, series
        )

        self.assertEqual(
            boot_resource_set.files.get(
                filetype=BOOT_RESOURCE_FILE_TYPE.BOOT_KERNEL
            ).filename,
            kernel,
        )
        self.assertEqual(
            boot_resource_set.files.get(
                filetype=BOOT_RESOURCE_FILE_TYPE.BOOT_INITRD
            ).filename,
            initrd,
        )
        self.assertEqual(
            boot_resource_set.files.get(
                filetype=BOOT_RESOURCE_FILE_TYPE.BOOT_DTB
            ).filename,
            boot_dbt,
        )

    def test_get_filenames_finds_subarch_when_generic(self):
        release = factory.make_default_ubuntu_release_bootable()
        arch = release.architecture.split("/")[0]
        osystem, series = release.name.split("/")
        boot_resource_set = release.get_latest_complete_set()
        factory.make_boot_resource_file_with_content(
            boot_resource_set,
            filetype=BOOT_RESOURCE_FILE_TYPE.BOOT_DTB,
            synced=[(self.region, -1)],
        )

        kernel, initrd, boot_dbt = get_boot_filenames(
            arch, "generic", osystem, series
        )

        self.assertEqual(
            boot_resource_set.files.get(
                filetype=BOOT_RESOURCE_FILE_TYPE.BOOT_KERNEL
            ).filename,
            kernel,
        )
        self.assertEqual(
            boot_resource_set.files.get(
                filetype=BOOT_RESOURCE_FILE_TYPE.BOOT_INITRD
            ).filename,
            initrd,
        )
        self.assertEqual(
            boot_resource_set.files.get(
                filetype=BOOT_RESOURCE_FILE_TYPE.BOOT_DTB
            ).filename,
            boot_dbt,
        )

    def test_returns_all_none_when_not_found(self):
        self.assertEqual(
            (None, None, None),
            get_boot_filenames(
                factory.make_name("arch"),
                factory.make_name("subarch"),
                factory.make_name("osystem"),
                factory.make_name("series"),
            ),
        )

    def test_returns_all_none_when_not_found_and_generic(self):
        self.assertEqual(
            (None, None, None),
            get_boot_filenames(
                factory.make_name("arch"),
                "generic",
                factory.make_name("osystem"),
                factory.make_name("series"),
            ),
        )

    def test_allows_no_boot_dtb(self):
        release = factory.make_default_ubuntu_release_bootable()
        arch, subarch = release.architecture.split("/")
        osystem, series = release.name.split("/")
        boot_resource_set = release.get_latest_complete_set()

        kernel, initrd, boot_dbt = get_boot_filenames(
            arch, subarch, osystem, series
        )

        self.assertEqual(
            boot_resource_set.files.get(
                filetype=BOOT_RESOURCE_FILE_TYPE.BOOT_KERNEL
            ).filename,
            kernel,
        )
        self.assertEqual(
            boot_resource_set.files.get(
                filetype=BOOT_RESOURCE_FILE_TYPE.BOOT_INITRD
            ).filename,
            initrd,
        )
        self.assertIsNone(boot_dbt)


class TestGetBootConfigForMachine(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        self.region = factory.make_RegionController()

    def test_get_boot_config_for_machine_builtin_image(self):
        machine = factory.make_Machine(
            status=NODE_STATUS.DEPLOYING,
            osystem="ubuntu",
            distro_series="focal",
            architecture="amd64/generic",
        )
        subarch = "ga-20.04"
        factory.make_usable_boot_resource(
            name="ubuntu/focal", architecture=f"amd64/{subarch}"
        )
        configs = Config.objects.get_configs(
            [
                "commissioning_osystem",
                "commissioning_distro_series",
                "enable_third_party_drivers",
                "default_min_hwe_kernel",
                "default_osystem",
                "default_distro_series",
                "kernel_opts",
                "use_rack_proxy",
                "maas_internal_domain",
                "remote_syslog",
                "maas_syslog_port",
            ]
        )

        osystem, series, config_arch, _, _ = get_boot_config_for_machine(
            machine, configs, "xinstall"
        )

        self.assertEqual("ubuntu", osystem)
        self.assertEqual("focal", series)
        self.assertEqual(subarch, config_arch)

    def test_get_boot_config_for_machine_new_custom_image(self):
        subarch = "ga-22.04"
        # We need a base image to be present. In fact, we always
        # needed that for the new image to boot.
        factory.make_usable_boot_resource(
            name="ubuntu/jammy", architecture=f"amd64/{subarch}"
        )
        boot_resource = factory.make_usable_boot_resource(
            architecture="amd64/generic",
            base_image="ubuntu/jammy",
        )
        machine = factory.make_Machine(
            architecture="amd64/generic",
            status=NODE_STATUS.DEPLOYING,
            osystem="custom",
            distro_series=boot_resource.name,
        )
        configs = Config.objects.get_configs(
            [
                "commissioning_osystem",
                "commissioning_distro_series",
                "enable_third_party_drivers",
                "default_min_hwe_kernel",
                "default_osystem",
                "default_distro_series",
                "kernel_opts",
                "use_rack_proxy",
                "maas_internal_domain",
                "remote_syslog",
                "maas_syslog_port",
            ]
        )

        osystem, series, config_arch, _, _ = get_boot_config_for_machine(
            machine, configs, "xinstall"
        )

        self.assertEqual("ubuntu", osystem)
        self.assertEqual("jammy", series)
        self.assertEqual(subarch, config_arch)

    def test_get_boot_config_for_machine_legacy_custom_image(self):
        subarch = "hwe-20.04"
        factory.make_usable_boot_resource(
            name="ubuntu/focal", architecture=f"amd64/{subarch}"
        )
        boot_resource = factory.make_BootResource(
            base_image="", architecture="amd64/generic"
        )
        machine = factory.make_Machine(
            architecture="amd64/generic",
            status=NODE_STATUS.DEPLOYING,
            osystem="custom",
            distro_series=boot_resource.name,
        )
        configs = Config.objects.get_configs(
            [
                "commissioning_osystem",
                "commissioning_distro_series",
                "enable_third_party_drivers",
                "default_min_hwe_kernel",
                "default_osystem",
                "default_distro_series",
                "kernel_opts",
                "use_rack_proxy",
                "maas_internal_domain",
                "remote_syslog",
                "maas_syslog_port",
            ]
        )

        osystem, series, config_arch, _, _ = get_boot_config_for_machine(
            machine, configs, "xinstall"
        )

        # legacy custom images should use the default commissioning image as a base image
        self.assertEqual(configs["commissioning_osystem"], osystem)
        self.assertEqual(configs["commissioning_distro_series"], series)
        self.assertEqual(subarch, config_arch)

    def test_get_boot_config_for_machine_ignores_machine_hwe_kernel_for_xinstall(
        self,
    ):
        # See LP:2013529
        subarch = "ga-22.04"
        machine_hwe_kernel = "hwe-20.04"  # Should be ignored

        # We need a base image to be present. In fact, we always
        # needed that for the new image to boot.
        factory.make_usable_boot_resource(
            name="ubuntu/jammy", architecture=f"amd64/{subarch}"
        )
        modern_custom_resource = factory.make_usable_boot_resource(
            architecture="amd64/generic",
            base_image="ubuntu/jammy",
        )
        modern_machine = factory.make_Machine(
            architecture="amd64/generic",
            status=NODE_STATUS.DEPLOYING,
            osystem="custom",
            distro_series=modern_custom_resource.name,
            hwe_kernel=machine_hwe_kernel,
        )

        legacy_custom_resource = factory.make_BootResource(
            base_image="", architecture="amd64/generic"
        )
        legacy_machine = factory.make_Machine(
            architecture="amd64/generic",
            status=NODE_STATUS.DEPLOYING,
            osystem="custom",
            distro_series=legacy_custom_resource.name,
            hwe_kernel=machine_hwe_kernel,
        )

        configs = Config.objects.get_configs(
            [
                "commissioning_osystem",
                "commissioning_distro_series",
                "enable_third_party_drivers",
                "default_min_hwe_kernel",
                "default_osystem",
                "default_distro_series",
                "kernel_opts",
                "use_rack_proxy",
                "maas_internal_domain",
                "remote_syslog",
                "maas_syslog_port",
            ]
        )
        legacy_subarch = f"ga-{configs['default_distro_series']}"
        factory.make_usable_boot_resource(
            name=f"{configs['default_osystem']}/{configs['default_distro_series']}",
            architecture=f"amd64/{legacy_subarch}",
        )

        osystem, series, config_arch, _, _ = get_boot_config_for_machine(
            modern_machine, configs, "xinstall"
        )
        self.assertEqual("ubuntu", osystem)
        self.assertEqual("jammy", series)
        self.assertEqual(subarch, config_arch)
        self.assertNotEqual(machine_hwe_kernel, config_arch)

        osystem, series, config_arch, _, _ = get_boot_config_for_machine(
            legacy_machine, configs, "xinstall"
        )
        self.assertEqual("ubuntu", osystem)
        self.assertEqual(configs["default_distro_series"], series)
        self.assertEqual(legacy_subarch, config_arch)
        self.assertNotEqual(machine_hwe_kernel, config_arch)

    def test_get_boot_config_for_machine_ignores_machine_hwe_kernel_for_commissioning(
        self,
    ):
        # See LP:2013529
        subarch = "ga-22.04"
        machine_hwe_kernel = "hwe-20.04"  # Should be ignored

        factory.make_usable_boot_resource(
            name="ubuntu/jammy", architecture=f"amd64/{subarch}"
        )
        boot_resource = factory.make_usable_boot_resource(
            architecture="amd64/generic",
            base_image="ubuntu/jammy",
        )
        machine = factory.make_Machine(
            architecture="amd64/generic",
            status=NODE_STATUS.DEPLOYING,
            osystem="custom",
            distro_series=boot_resource.name,
            hwe_kernel=machine_hwe_kernel,
        )

        configs = Config.objects.get_configs(
            [
                "commissioning_osystem",
                "commissioning_distro_series",
                "enable_third_party_drivers",
                "default_min_hwe_kernel",
                "default_osystem",
                "default_distro_series",
                "kernel_opts",
                "use_rack_proxy",
                "maas_internal_domain",
                "remote_syslog",
                "maas_syslog_port",
            ]
        )
        legacy_subarch = f"ga-{configs['default_distro_series']}"
        factory.make_usable_boot_resource(
            name=f"{configs['default_osystem']}/{configs['default_distro_series']}",
            architecture=f"amd64/{legacy_subarch}",
        )

        osystem, series, config_arch, _, _ = get_boot_config_for_machine(
            machine, configs, "commissioning"
        )
        self.assertEqual(configs["commissioning_osystem"], osystem)
        self.assertEqual(configs["commissioning_distro_series"], series)
        self.assertEqual(legacy_subarch, config_arch)
        self.assertNotEqual(machine_hwe_kernel, config_arch)

    def test_get_boot_config_for_custom_ephemeral_deployments(
        self,
    ):
        subarch = "generic"

        factory.make_usable_boot_resource(
            name="centos/8", architecture=f"amd64/{subarch}"
        )
        machine = factory.make_Machine(
            architecture="amd64/generic",
            status=NODE_STATUS.DEPLOYING,
            osystem="centos",
            distro_series="8",
            ephemeral_deploy=True,
        )

        configs = Config.objects.get_configs(
            [
                "commissioning_osystem",
                "commissioning_distro_series",
                "enable_third_party_drivers",
                "default_min_hwe_kernel",
                "default_osystem",
                "default_distro_series",
                "kernel_opts",
                "use_rack_proxy",
                "maas_internal_domain",
                "remote_syslog",
                "maas_syslog_port",
            ]
        )
        legacy_subarch = f"ga-{configs['default_distro_series']}"
        factory.make_usable_boot_resource(
            name=f"{configs['default_osystem']}/{configs['default_distro_series']}",
            architecture=f"amd64/{legacy_subarch}",
        )

        osystem, series, config_arch, _, _ = get_boot_config_for_machine(
            machine, configs, "local"
        )
        self.assertEqual("centos", osystem)
        self.assertEqual("8", series)
        self.assertEqual("generic", config_arch)

    def test_get_boot_config_for_machine_centos(self):
        subarch = "ga-20.04"
        # We need a base image to be present. In fact, we always
        # needed that for the new image to boot.
        factory.make_default_ubuntu_release_bootable(arch=f"amd64/{subarch}")
        factory.make_usable_boot_resource(
            name="centos/7",
            architecture="amd64/generic",
        )
        machine = factory.make_Machine(
            architecture="amd64/generic",
            status=NODE_STATUS.DEPLOYING,
            osystem="centos",
            distro_series="7",
        )
        configs = Config.objects.get_configs(
            [
                "commissioning_osystem",
                "commissioning_distro_series",
                "enable_third_party_drivers",
                "default_min_hwe_kernel",
                "default_osystem",
                "default_distro_series",
                "kernel_opts",
                "use_rack_proxy",
                "maas_internal_domain",
                "remote_syslog",
                "maas_syslog_port",
            ]
        )

        (
            osystem,
            series,
            config_arch,
            final_osystem,
            final_series,
        ) = get_boot_config_for_machine(machine, configs, "xinstall")

        self.assertEqual(configs["commissioning_osystem"], osystem)
        self.assertEqual(configs["commissioning_distro_series"], series)
        self.assertEqual(subarch, config_arch)
        self.assertEqual("centos", final_osystem)
        self.assertEqual("7", final_series)


class TestGetNodeFromMacOrHardwareUUID(MAASServerTestCase):
    def test_get_node_from_mac_or_hardware_uuid_with_regular_mac(self):
        node = factory.make_Node_with_Interface_on_Subnet()
        iface = node.current_config.interface_set.first()
        result = get_node_from_mac_or_hardware_uuid(mac=iface.mac_address)
        self.assertEqual(node, result)

    def test_get_node_from_mac_or_hardware_uuid_with_dash_mac(self):
        node = factory.make_Node_with_Interface_on_Subnet()
        iface = node.current_config.interface_set.first()
        result = get_node_from_mac_or_hardware_uuid(
            mac=iface.mac_address.replace(":", "-")
        )
        self.assertEqual(node, result)

    def test_get_node_from_mac_or_hardware_uuid_with_mac_and_hardware_uuid(
        self,
    ):
        node = factory.make_Node_with_Interface_on_Subnet()
        iface = node.current_config.interface_set.first()
        result = get_node_from_mac_or_hardware_uuid(
            mac=iface.mac_address, hardware_uuid=node.hardware_uuid
        )
        self.assertEqual(node, result)

    def test_get_node_from_mac_or_hardware_uuid_with_hardware_uuid(self):
        node = factory.make_Node_with_Interface_on_Subnet()
        result = get_node_from_mac_or_hardware_uuid(
            hardware_uuid=node.hardware_uuid
        )
        self.assertEqual(node, result)
