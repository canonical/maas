# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver Switch model."""


from crochet import wait_for
from django.db.utils import IntegrityError

from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase

wait_for_reactor = wait_for(30)  # 30 seconds.


class TestSwitch(MAASServerTestCase):
    def test_str(self):
        # A Switch object string representation references the parent node
        # hostname.
        node = factory.make_Machine(hostname="foobar")
        switch = factory.make_Switch(node=node)
        self.assertEqual("Switch (foobar)", str(switch))

    def test_device(self):
        # A Switch object can be based on a device node.
        device = factory.make_Device()
        switch = factory.make_Switch(node=device)
        self.assertEqual(device.as_node(), switch.node)

    def test_machine(self):
        # A Switch object can be based on a machine node.
        machine = factory.make_Machine()
        switch = factory.make_Switch(node=machine)
        self.assertEqual(machine.as_node(), switch.node)

    def test_nos_driver(self):
        # A Switch object can have nos_driver set to a string.
        switch = factory.make_Switch(nos_driver="flexswitch")
        self.assertEqual("flexswitch", switch.nos_driver)

    def test_node_unique(self):
        # We can only ever have one Switch object for a particular node
        # and nos_driver.
        switch1 = factory.make_Switch()
        self.assertRaises(
            IntegrityError, factory.make_Switch, node=switch1.node
        )

    def test_nos_parameters(self):
        # A Switch object can have nos_parameters set to an object
        # that can be serialized to a JSON string and back.
        switch = factory.make_Switch(nos_parameters={"foo": ["bar", 1]})
        self.assertEqual({"foo": ["bar", 1]}, switch.nos_parameters)
