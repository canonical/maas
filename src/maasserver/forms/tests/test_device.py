# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for device forms."""


from django.http import HttpRequest
from django.http.request import QueryDict
from testtools.matchers import Contains, Equals

from maasserver.forms import DeviceForm, DeviceWithMACsForm
from maasserver.models import Device, Interface
from maasserver.testing.factory import factory
from maasserver.testing.fixtures import RBACEnabled
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.forms import get_QueryDict
from maasserver.utils.orm import get_one, reload_object


class TestDeviceForm(MAASServerTestCase):
    def test_contains_limited_set_of_fields(self):
        form = DeviceForm()

        self.assertItemsEqual(
            [
                "hostname",
                "description",
                "domain",
                "parent",
                "disable_ipv4",
                "swap_size",
                "zone",
            ],
            list(form.fields),
        )

    def test_changes_device_parent(self):
        device = factory.make_Device()
        parent = factory.make_Node()

        form = DeviceForm(data={"parent": parent.system_id}, instance=device)
        form.save()
        reload_object(device)
        reload_object(parent)

        self.assertEqual(parent, device.parent)

    def test_has_perm_no_rbac(self):
        form = DeviceForm()
        self.assertTrue(form.has_perm(factory.make_User()))

    def test_has_perm_rbac_no_permision(self):
        self.useFixture(RBACEnabled())
        form = DeviceForm()
        self.assertFalse(form.has_perm(factory.make_User()))

    def test_has_perm_rbac_global_admin(self):
        self.useFixture(RBACEnabled())
        user = factory.make_admin()
        form = DeviceForm()
        self.assertTrue(form.has_perm(user))

    def test_has_perm_rbac_permission_on_pool(self):
        rbac = self.useFixture(RBACEnabled())
        user = factory.make_User()
        rbac.store.allow(
            user.username, factory.make_ResourcePool(), "admin-machines"
        )
        form = DeviceForm()
        self.assertTrue(form.has_perm(user))

    def test_has_perm_rbac_read_permission_on_pool(self):
        rbac = self.useFixture(RBACEnabled())
        user = factory.make_User()
        rbac.store.allow(user.username, factory.make_ResourcePool(), "view")
        form = DeviceForm()
        self.assertFalse(form.has_perm(user))


class TestDeviceWithMACsForm(MAASServerTestCase):
    def make_request(self):
        """Return a :class:`HttpRequest` with the given parameters."""
        request = HttpRequest()
        request.user = factory.make_User()
        return request

    def test_contains_mac_addresses_field_and_converts_non_querydict(self):
        form = DeviceWithMACsForm(data={})
        self.assertThat(form.fields, Contains("mac_addresses"))
        self.assertIsInstance(form.data, QueryDict)

    def test_creates_device_with_mac(self):
        hostname = factory.make_name("device")
        mac = factory.make_mac_address()
        form = DeviceWithMACsForm(
            data=get_QueryDict({"hostname": hostname, "mac_addresses": mac}),
            request=self.make_request(),
        )
        self.assertTrue(form.is_valid(), dict(form.errors))
        form.save()
        device = get_one(Device.objects.filter(hostname=hostname))
        self.assertThat(device.hostname, Equals(hostname))
        iface = get_one(Interface.objects.filter(mac_address=mac))
        self.assertThat(iface.node, Equals(device))

    def test_creates_device_with_macs(self):
        hostname = factory.make_name("device")
        mac1 = factory.make_mac_address()
        mac2 = factory.make_mac_address()
        form = DeviceWithMACsForm(
            data=get_QueryDict(
                {"hostname": hostname, "mac_addresses": [mac1, mac2]}
            ),
            request=self.make_request(),
        )
        self.assertTrue(form.is_valid(), dict(form.errors))
        form.save()
        device = get_one(Device.objects.filter(hostname=hostname))
        self.assertThat(device.hostname, Equals(hostname))
        iface = get_one(Interface.objects.filter(mac_address=mac1))
        self.assertThat(iface.node, Equals(device))
        iface = get_one(Interface.objects.filter(mac_address=mac2))
        self.assertThat(iface.node, Equals(device))

    def test_creates_device_with_parent_inherits_parents_domain(self):
        parent = factory.make_Node()
        hostname = factory.make_name("device")
        mac1 = factory.make_mac_address()
        mac2 = factory.make_mac_address()
        form = DeviceWithMACsForm(
            data=get_QueryDict(
                {
                    "hostname": hostname,
                    "mac_addresses": [mac1, mac2],
                    "parent": parent.system_id,
                }
            ),
            request=self.make_request(),
        )
        self.assertTrue(form.is_valid(), dict(form.errors))
        form.save()
        device = get_one(Device.objects.filter(hostname=hostname))
        self.assertThat(device.hostname, Equals(hostname))
        self.assertThat(device.domain, Equals(parent.domain))
        iface = get_one(Interface.objects.filter(mac_address=mac1))
        self.assertThat(iface.node, Equals(device))
        iface = get_one(Interface.objects.filter(mac_address=mac2))
        self.assertThat(iface.node, Equals(device))

    def test_creates_device_with_domain_and_parent(self):
        parent = factory.make_Node()
        hostname = factory.make_name("device")
        mac1 = factory.make_mac_address()
        mac2 = factory.make_mac_address()
        domain = factory.make_Domain()
        form = DeviceWithMACsForm(
            data=get_QueryDict(
                {
                    "hostname": hostname,
                    "mac_addresses": [mac1, mac2],
                    "parent": parent.system_id,
                    "domain": domain.name,
                }
            ),
            request=self.make_request(),
        )
        self.assertTrue(form.is_valid(), dict(form.errors))
        form.save()
        device = get_one(Device.objects.filter(hostname=hostname))
        self.assertThat(device.hostname, Equals(hostname))
        self.assertThat(device.domain, Equals(domain))
        iface = get_one(Interface.objects.filter(mac_address=mac1))
        self.assertThat(iface.node, Equals(device))
        iface = get_one(Interface.objects.filter(mac_address=mac2))
        self.assertThat(iface.node, Equals(device))
