# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import random

from django.core.exceptions import ValidationError

from maasserver.models.virtualmachine import VirtualMachine
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestVirtualMachine(MAASServerTestCase):
    def test_instantiate_defaults(self):
        bmc = factory.make_BMC(power_type="lxd")
        vm = VirtualMachine(identifier="vm1", bmc=bmc)
        vm.save()
        self.assertEqual(vm.identifier, "vm1")
        self.assertIs(vm.bmc, bmc)
        self.assertEqual(vm.unpinned_cores, 0)
        self.assertEqual(vm.pinned_cores, [])
        self.assertEqual(vm.memory, 0)
        self.assertFalse(vm.hugepages_backed)
        self.assertIsNone(vm.machine)

    def test_instantiate_extra_fields(self):
        memory = 1024 * random.randint(1, 256)
        machine = factory.make_Machine()
        hugepages_backed = factory.pick_bool()
        vm = VirtualMachine(
            identifier="vm1",
            bmc=factory.make_BMC(power_type="lxd"),
            memory=memory,
            machine=machine,
            hugepages_backed=hugepages_backed,
        )
        vm.save()
        self.assertEqual(vm.unpinned_cores, 0)
        self.assertEqual(vm.pinned_cores, [])
        self.assertEqual(vm.memory, memory)
        self.assertEqual(vm.hugepages_backed, hugepages_backed)
        self.assertIs(vm.machine, machine)

    def test_instantiate_pinned_cores(self):
        vm = factory.make_VirtualMachine(pinned_cores=[1, 2, 3])
        self.assertEqual(vm.pinned_cores, [1, 2, 3])

    def test_instantiate_unpinned_cores(self):
        vm = factory.make_VirtualMachine(unpinned_cores=4)
        self.assertEqual(vm.unpinned_cores, 4)

    def test_instantiate_validate_cores(self):
        self.assertRaises(
            ValidationError,
            factory.make_VirtualMachine,
            pinned_cores=[1, 2, 3],
            unpinned_cores=4,
        )

    def test_machine_virtualmachine(self):
        machine = factory.make_Machine()
        vm = VirtualMachine.objects.create(
            identifier="vm1",
            bmc=factory.make_BMC(power_type="lxd"),
            machine=machine,
        )
        self.assertIs(machine.virtualmachine, vm)
