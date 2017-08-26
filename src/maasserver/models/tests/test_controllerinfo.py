# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver ControllerInfo model."""

__all__ = []

from crochet import wait_for
from maasserver.models import ControllerInfo
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from testtools.matchers import Equals


wait_for_reactor = wait_for(30)  # 30 seconds.


class TestControllerInfo(MAASServerTestCase):

    def test_str(self):
        controller = factory.make_RackController(hostname="foobar")
        info, _ = ControllerInfo.objects.update_or_create(node=controller)
        self.assertEqual("ControllerInfo (foobar)", str(info))

    def test_controllerinfo_set_version(self):
        controller = factory.make_RackController()
        ControllerInfo.objects.set_version(controller, "2.3.0")
        self.assertThat(controller.version, Equals("2.3.0"))

    def test_controllerinfo_set_infterface_update_info(self):
        controller = factory.make_RackController()
        interfaces = {
            'eth0': {}
        }
        hints = ["a", "b", "c"]
        ControllerInfo.objects.set_interface_update_info(
            controller, interfaces, hints)
        self.assertThat(controller.interfaces, Equals(interfaces))
        self.assertThat(controller.interface_update_hints, Equals(hints))
