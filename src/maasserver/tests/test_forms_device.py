# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for device forms."""

__all__ = []

from maasserver.forms import DeviceForm
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object


class TestDeviceForm(MAASServerTestCase):

    def test_contains_limited_set_of_fields(self):
        form = DeviceForm()

        self.assertItemsEqual(
            [
                'hostname',
                'domain',
                'parent',
                'disable_ipv4',
                'swap_size',
            ], list(form.fields))

    def test_changes_device_parent(self):
        device = factory.make_Device()
        parent = factory.make_Node()

        form = DeviceForm(
            data={
                'parent': parent.system_id,
                },
            instance=device)
        form.save()
        reload_object(device)
        reload_object(parent)

        self.assertEqual(parent, device.parent)
