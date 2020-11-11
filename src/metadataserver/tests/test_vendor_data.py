# Copyright 2016-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `metadataserver.vendor_data`."""


import random

from netaddr import IPAddress
from testtools.matchers import (
    Contains,
    ContainsDict,
    Equals,
    HasLength,
    Is,
    IsInstance,
    KeysEqual,
    MatchesDict,
    Not,
)
import yaml

from maasserver.enum import NODE_STATUS
from maasserver.models import Config, NodeMetadata
from maasserver.node_status import COMMISSIONING_LIKE_STATUSES
from maasserver.server_address import get_maas_facing_server_host
from maasserver.testing.factory import factory
from maasserver.testing.fixtures import RBACEnabled
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import MockNotCalled
from metadataserver.vendor_data import (
    generate_ephemeral_deployment_network_configuration,
    generate_ntp_configuration,
    generate_rack_controller_configuration,
    generate_system_info,
    get_vendor_data,
)
from provisioningserver.utils import version


class TestGetVendorData(MAASServerTestCase):
    """Tests for `get_vendor_data`."""

    def test_returns_dict(self):
        node = factory.make_Node()
        self.assertThat(get_vendor_data(node, None), IsInstance(dict))

    def test_includes_no_system_information_if_no_default_user(self):
        node = factory.make_Node(owner=factory.make_User())
        vendor_data = get_vendor_data(node, None)
        self.assertThat(vendor_data, Not(Contains("system_info")))

    def test_includes_system_information_if_default_user(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner, default_user=owner)
        vendor_data = get_vendor_data(node, None)
        self.assertThat(
            vendor_data,
            ContainsDict(
                {
                    "system_info": MatchesDict(
                        {"default_user": KeysEqual("name", "gecos")}
                    )
                }
            ),
        )

    def test_includes_ntp_server_information(self):
        Config.objects.set_config("ntp_external_only", True)
        Config.objects.set_config("ntp_servers", "foo bar")
        node = factory.make_Node()
        vendor_data = get_vendor_data(node, None)
        self.assertThat(
            vendor_data,
            ContainsDict(
                {"ntp": Equals({"servers": [], "pools": ["bar", "foo"]})}
            ),
        )


class TestGenerateSystemInfo(MAASServerTestCase):
    """Tests for `generate_system_info`."""

    def test_yields_nothing_when_node_has_no_owner(self):
        node = factory.make_Node()
        self.assertThat(node.owner, Is(None))
        configuration = generate_system_info(node)
        self.assertThat(dict(configuration), Equals({}))

    def test_yields_nothing_when_owner_and_no_default_user(self):
        node = factory.make_Node()
        self.assertThat(node.owner, Is(None))
        self.assertThat(node.default_user, Is(""))
        configuration = generate_system_info(node)
        self.assertThat(dict(configuration), Equals({}))

    def test_yields_basic_system_info_when_node_owned_with_default_user(self):
        owner = factory.make_User()
        owner.first_name = "First"
        owner.last_name = "Last"
        owner.save()
        node = factory.make_Node(owner=owner, default_user=owner)
        configuration = generate_system_info(node)
        self.assertThat(
            dict(configuration),
            Equals(
                {
                    "system_info": {
                        "default_user": {
                            "name": owner.username,
                            "gecos": "First Last,,,,",
                        }
                    }
                }
            ),
        )


class TestGenerateNTPConfiguration(MAASServerTestCase):
    """Tests for `generate_ntp_configuration`."""

    def test_external_only_yields_nothing_when_no_ntp_servers_defined(self):
        Config.objects.set_config("ntp_external_only", True)
        Config.objects.set_config("ntp_servers", "")
        configuration = generate_ntp_configuration(node=factory.make_Node())
        self.assertThat(dict(configuration), Equals({}))

    def test_external_only_yields_all_ntp_servers_when_defined(self):
        Config.objects.set_config("ntp_external_only", True)
        ntp_hosts = factory.make_hostname(), factory.make_hostname()
        ntp_addrs = factory.make_ipv4_address(), factory.make_ipv6_address()
        ntp_servers = ntp_hosts + ntp_addrs
        Config.objects.set_config("ntp_servers", " ".join(ntp_servers))
        configuration = generate_ntp_configuration(node=factory.make_Node())
        self.assertThat(
            dict(configuration),
            Equals(
                {
                    "ntp": {
                        "servers": sorted(ntp_addrs, key=IPAddress),
                        "pools": sorted(ntp_hosts),
                    }
                }
            ),
        )

    def test_yields_nothing_when_machine_has_no_boot_cluster_address(self):
        Config.objects.set_config("ntp_external_only", False)
        machine = factory.make_Machine()
        machine.boot_cluster_ip = None
        machine.save()
        configuration = generate_ntp_configuration(machine)
        self.assertThat(dict(configuration), Equals({}))

    def test_yields_boot_cluster_address_when_machine_has_booted(self):
        Config.objects.set_config("ntp_external_only", False)

        machine = factory.make_Machine()
        address = factory.make_StaticIPAddress(
            interface=factory.make_Interface(node=machine)
        )

        rack_primary = factory.make_RackController(subnet=address.subnet)
        rack_primary_address = factory.make_StaticIPAddress(
            interface=factory.make_Interface(node=rack_primary),
            subnet=address.subnet,
        )

        rack_secondary = factory.make_RackController(subnet=address.subnet)
        rack_secondary_address = factory.make_StaticIPAddress(
            interface=factory.make_Interface(node=rack_secondary),
            subnet=address.subnet,
        )

        vlan = address.subnet.vlan
        vlan.primary_rack = rack_primary
        vlan.secondary_rack = rack_secondary
        vlan.dhcp_on = True
        vlan.save()

        configuration = generate_ntp_configuration(machine)
        self.assertThat(
            dict(configuration),
            Equals(
                {
                    "ntp": {
                        "servers": sorted(
                            (
                                rack_primary_address.ip,
                                rack_secondary_address.ip,
                            ),
                            key=IPAddress,
                        ),
                        "pools": [],
                    }
                }
            ),
        )


class TestGenerateRackControllerConfiguration(MAASServerTestCase):
    """Tests for `generate_ntp_rack_controller_configuration`."""

    def test_yields_nothing_when_node_is_not_netboot_disabled(self):
        configuration = generate_rack_controller_configuration(
            node=factory.make_Node(osystem="ubuntu"),
            proxy="http://proxy.example.com/",
        )
        self.assertThat(dict(configuration), Equals({}))

    def test_yields_nothing_when_node_is_not_ubuntu(self):
        tag = factory.make_Tag(name="switch")
        node = factory.make_Node(osystem="centos", netboot=False)
        node.tags.add(tag)
        configuration = generate_rack_controller_configuration(
            node, proxy="http://proxy.example.com/"
        )
        self.assertThat(dict(configuration), Equals({}))

    def test_yields_configuration_with_ubuntu(self):
        tag = factory.make_Tag(name="wedge100")
        node = factory.make_Node(osystem="ubuntu", netboot=False)
        node.tags.add(tag)
        configuration = generate_rack_controller_configuration(
            node, proxy="http://proxy.example.com/"
        )
        secret = "1234"
        Config.objects.set_config("rpc_shared_secret", secret)
        channel = version.get_maas_version_track_channel()
        maas_url = "http://%s:5240/MAAS" % get_maas_facing_server_host(
            node.get_boot_rack_controller()
        )
        cmd = "/bin/snap/maas init --mode rack"

        self.assertThat(
            dict(configuration),
            KeysEqual(
                {
                    "runcmd": [
                        f"snap install maas --channel={channel}",
                        "%s --maas-url %s --secret %s"
                        % (cmd, maas_url, secret),
                    ]
                }
            ),
        )

    def test_yields_nothing_when_machine_install_rackd_false(self):
        node = factory.make_Node(osystem="ubuntu", netboot=False)
        node.install_rackd = False
        configuration = generate_rack_controller_configuration(
            node, proxy="http://proxy.example.com/"
        )
        self.assertThat(dict(configuration), Equals({}))

    def test_yields_configuration_when_machine_install_rackd_true(self):
        node = factory.make_Node(osystem="ubuntu", netboot=False)
        node.install_rackd = True
        proxy = "http://proxy.example.com/"
        configuration = generate_rack_controller_configuration(
            node, proxy=proxy
        )
        secret = "1234"
        Config.objects.set_config("rpc_shared_secret", secret)
        channel = version.get_maas_version_track_channel()
        maas_url = "http://%s:5240/MAAS" % get_maas_facing_server_host(
            node.get_boot_rack_controller()
        )
        cmd = "/bin/snap/maas init --mode rack"

        self.assertThat(
            dict(configuration),
            KeysEqual(
                {
                    "runcmd": [
                        "snap set system proxy.http=%s proxy.https=%s"
                        % (proxy, proxy),
                        f"snap install maas --channel={channel}",
                        "%s --maas-url %s --secret %s"
                        % (cmd, maas_url, secret),
                    ]
                }
            ),
        )

    def test_yields_configuration_when_machine_install_kvm_true(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING, osystem="ubuntu", netboot=False
        )
        node.install_kvm = True
        configuration = get_vendor_data(node, None)
        config = str(dict(configuration))
        self.assertThat(config, Contains("virsh"))
        self.assertThat(config, Contains("ssh_pwauth"))
        self.assertThat(config, Contains("rbash"))
        self.assertThat(config, Contains("libvirt-daemon-system"))
        self.assertThat(config, Contains("ForceCommand"))
        self.assertThat(config, Contains("libvirt-clients"))
        # Check that a password was saved for the pod-to-be.
        virsh_password_meta = NodeMetadata.objects.filter(
            node=node, key="virsh_password"
        ).first()
        self.assertThat(virsh_password_meta.value, HasLength(32))

    def test_includes_smt_off_for_install_kvm_on_ppc64(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING,
            osystem="ubuntu",
            netboot=False,
            architecture="ppc64el/generic",
        )
        node.install_kvm = True
        configuration = get_vendor_data(node, None)
        config = dict(configuration)
        self.assertThat(
            config["runcmd"],
            Contains(
                [
                    "sh",
                    "-c",
                    'printf "'
                    "#!/bin/sh\\n"
                    "ppc64_cpu --smt=off\\n"
                    "exit 0\\n"
                    '"  >> /etc/rc.local',
                ]
            ),
        )
        self.assertThat(
            config["runcmd"], Contains(["chmod", "+x", "/etc/rc.local"])
        )
        self.assertThat(config["runcmd"], Contains(["/etc/rc.local"]))


class TestGenerateEphemeralNetplanLockRemoval(MAASServerTestCase):
    """Tests for `generate_ephemeral_netplan_lock_removal`."""

    def test_does_nothing_if_deploying(self):
        # MAAS transitions a machine from DEPLOYING to DEPLOYED after
        # user_data has been requested. Make sure deploying nodes don't
        # get this config.
        node = factory.make_Node(status=NODE_STATUS.DEPLOYING)
        configuration = get_vendor_data(node, None)
        config = dict(configuration)
        self.assertNotIn("runcmd", config)

    def test_removes_lock_when_ephemeral(self):
        node = factory.make_Node(
            status=random.choice(COMMISSIONING_LIKE_STATUSES)
        )
        configuration = get_vendor_data(node, None)
        config = dict(configuration)
        self.assertThat(config["runcmd"], Contains("rm -rf /run/netplan"))


class TestGenerateEphemeralDeploymentNetworkConfiguration(MAASServerTestCase):
    """Tests for `generate_ephemeral_deployment_network_configuration`."""

    def test_yields_nothing_when_node_is_not_ephemeral_deployment(self):
        node = factory.make_Node()
        configuration = generate_ephemeral_deployment_network_configuration(
            node
        )
        self.assertThat(dict(configuration), Equals({}))

    def test_yields_configuration_when_node_is_ephemeral_deployment(self):
        node = factory.make_Node(
            with_boot_disk=False,
            ephemeral_deploy=True,
            status=NODE_STATUS.DEPLOYING,
        )
        configuration = get_vendor_data(node, None)
        config = dict(configuration)
        self.assertThat(
            config["write_files"][0]["path"],
            Contains("/etc/netplan/50-maas.yaml"),
        )
        # Make sure netplan's lock is removed before applying the config
        self.assertEquals(config["runcmd"][0], "rm -rf /run/netplan")
        self.assertEquals(config["runcmd"][1], "netplan apply --debug")


class TestGenerateVcenterConfiguration(MAASServerTestCase):
    """Tests for `generate_vcenter_configuration`."""

    def test_does_nothing_if_not_vmware(self):
        mock_get_configs = self.patch(Config.objects, "get_configs")
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING, owner=factory.make_admin()
        )
        config = get_vendor_data(node, None)
        self.assertThat(mock_get_configs, MockNotCalled())
        self.assertDictEqual({}, config)

    def test_returns_nothing_if_no_values_set(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING,
            osystem="esxi",
            owner=factory.make_admin(),
        )
        node.nodemetadata_set.create(key="vcenter_registration", value="True")
        config = get_vendor_data(node, None)
        self.assertDictEqual({}, config)

    def test_returns_vcenter_yaml(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING,
            osystem="esxi",
            owner=factory.make_admin(),
        )
        node.nodemetadata_set.create(key="vcenter_registration", value="True")
        vcenter = {
            "vcenter_server": factory.make_name("vcenter_server"),
            "vcenter_username": factory.make_name("vcenter_username"),
            "vcenter_password": factory.make_name("vcenter_password"),
            "vcenter_datacenter": factory.make_name("vcenter_datacenter"),
        }
        for key, value in vcenter.items():
            Config.objects.set_config(key, value)
        config = get_vendor_data(node, None)
        self.assertDictEqual(
            {
                "write_files": [
                    {
                        "content": yaml.safe_dump(vcenter),
                        "path": "/altbootbank/maas/vcenter.yaml",
                    }
                ]
            },
            config,
        )

    def test_returns_vcenter_yaml_if_rbac_admin(self):
        rbac = self.useFixture(RBACEnabled())
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING,
            osystem="esxi",
            owner=factory.make_User(),
        )
        node.nodemetadata_set.create(key="vcenter_registration", value="True")
        rbac.store.add_pool(node.pool)
        rbac.store.allow(node.owner.username, node.pool, "admin-machines")
        vcenter = {
            "vcenter_server": factory.make_name("vcenter_server"),
            "vcenter_username": factory.make_name("vcenter_username"),
            "vcenter_password": factory.make_name("vcenter_password"),
            "vcenter_datacenter": factory.make_name("vcenter_datacenter"),
        }
        for key, value in vcenter.items():
            Config.objects.set_config(key, value)
        config = get_vendor_data(node, None)
        self.assertDictEqual(
            {
                "write_files": [
                    {
                        "content": yaml.safe_dump(vcenter),
                        "path": "/altbootbank/maas/vcenter.yaml",
                    }
                ]
            },
            config,
        )

    def test_returns_nothing_if_rbac_user(self):
        rbac = self.useFixture(RBACEnabled())
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING,
            osystem="esxi",
            owner=factory.make_User(),
        )
        node.nodemetadata_set.create(key="vcenter_registration", value="True")
        rbac.store.add_pool(node.pool)
        rbac.store.allow(node.owner.username, node.pool, "deploy-machines")
        vcenter = {
            "vcenter_server": factory.make_name("vcenter_server"),
            "vcenter_username": factory.make_name("vcenter_username"),
            "vcenter_password": factory.make_name("vcenter_password"),
            "vcenter_datacenter": factory.make_name("vcenter_datacenter"),
        }
        for key, value in vcenter.items():
            Config.objects.set_config(key, value)
        config = get_vendor_data(node, None)
        self.assertDictEqual({}, config)

    def test_returns_nothing_if_no_user(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYING, osystem="esxi")
        for i in ["server", "username", "password", "datacenter"]:
            key = "vcenter_%s" % i
            Config.objects.set_config(key, factory.make_name(key))
        config = get_vendor_data(node, None)
        self.assertDictEqual({}, config)

    def test_returns_nothing_if_user(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING,
            osystem="esxi",
            owner=factory.make_User(),
        )
        for i in ["server", "username", "password", "datacenter"]:
            key = "vcenter_%s" % i
            Config.objects.set_config(key, factory.make_name(key))
        config = get_vendor_data(node, None)
        self.assertDictEqual({}, config)

    def test_returns_nothing_if_vcenter_registration_not_set(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING,
            osystem="esxi",
            owner=factory.make_admin(),
        )
        for i in ["server", "username", "password", "datacenter"]:
            key = "vcenter_%s" % i
            Config.objects.set_config(key, factory.make_name(key))
        config = get_vendor_data(node, None)
        self.assertDictEqual({}, config)
