# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import http.client

from django.urls import reverse

from maasserver.models.node import Machine
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory


def get_switch_boot_order_uri(system_id):
    return reverse("switch_boot_order_handler", args=[system_id])


class TestSwitchBootOrderHandler(APITestCase.ForUser):
    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/switch-boot-order/abc/",
            get_switch_boot_order_uri("abc"),
        )

    def test_update(self):
        self.patch(Machine, "set_boot_order")
        machine = factory.make_Machine()

        uri = get_switch_boot_order_uri(machine.system_id)
        response = self.client.put(uri, {"network_boot": False})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        machine.set_boot_order.assert_called_once_with(network_boot=False)
