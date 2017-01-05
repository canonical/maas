# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for chassis forms."""

__all__ = []

import random

from maasserver import forms
from maasserver.clusterrpc.driver_parameters import (
    DriverType,
    get_driver_choices,
)
from maasserver.exceptions import ChassisProblem
from maasserver.forms import ChassisForm
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from provisioningserver.drivers.chassis import (
    DiscoveredChassis,
    DiscoveredChassisHints,
)
from testtools.matchers import (
    Equals,
    Is,
    MatchesAll,
    MatchesStructure,
    Not,
)


class TestChassisForm(MAASServerTestCase):

    def test_contains_limited_set_of_fields(self):
        form = ChassisForm()
        self.assertItemsEqual(
            [
                'hostname',
                'chassis_type',
                'chassis_parameters',
            ], list(form.fields))

    def test_creates_chassis_with_discovered_information(self):
        discovered_chassis = DiscoveredChassis(
            cores=random.randint(2, 4), memory=random.randint(1024, 4096),
            local_storage=random.randint(1024, 1024 * 1024),
            cpu_speed=random.randint(2048, 4048),
            hints=DiscoveredChassisHints(
                cores=random.randint(2, 4), memory=random.randint(1024, 4096),
                local_storage=random.randint(1024, 1024 * 1024),
                cpu_speed=random.randint(2048, 4048)))
        discovered_rack_1 = factory.make_RackController()
        discovered_rack_2 = factory.make_RackController()
        failed_rack = factory.make_RackController()
        self.patch(forms, "discover_chassis").return_value = ({
            discovered_rack_1.system_id: discovered_chassis,
            discovered_rack_2.system_id: discovered_chassis,
        }, {
            failed_rack.system_id: factory.make_exception(),
        })
        chassis_type = random.choice(
            get_driver_choices(driver_type=DriverType.chassis))[0]
        form = ChassisForm(data={
            'chassis_type': chassis_type,
        })
        self.assertTrue(form.is_valid(), form._errors)
        chassis = form.save()
        self.assertThat(chassis, MatchesStructure(
            hostname=MatchesAll(Not(Is(None)), Not(Equals(''))),
            cpu_count=Equals(discovered_chassis.cores),
            memory=Equals(discovered_chassis.memory),
            cpu_speed=Equals(discovered_chassis.cpu_speed),
            power_type=Equals(chassis_type),
        ))
        routable_racks = [
            relation.rack_controller
            for relation in chassis.bmc.routable_rack_relationships.all()
            if relation.routable
        ]
        not_routable_racks = [
            relation.rack_controller
            for relation in chassis.bmc.routable_rack_relationships.all()
            if not relation.routable
        ]
        self.assertItemsEqual(
            routable_racks, [discovered_rack_1, discovered_rack_2])
        self.assertItemsEqual(not_routable_racks, [failed_rack])

    def test_raises_unable_to_discover_because_no_racks(self):
        self.patch(forms, "discover_chassis").return_value = ({}, {})
        chassis_type = random.choice(
            get_driver_choices(driver_type=DriverType.chassis))[0]
        form = ChassisForm(data={
            'chassis_type': chassis_type,
        })
        self.assertTrue(form.is_valid(), form._errors)
        error = self.assertRaises(ChassisProblem, form.save)
        self.assertEquals(
            "No rack controllers connected to discover a chassis.", str(error))

    def test_raises_exception_from_rack_controller(self):
        failed_rack = factory.make_RackController()
        exc = factory.make_exception()
        self.patch(forms, "discover_chassis").return_value = ({}, {
            failed_rack.system_id: exc,
        })
        chassis_type = random.choice(
            get_driver_choices(driver_type=DriverType.chassis))[0]
        form = ChassisForm(data={
            'chassis_type': chassis_type,
        })
        self.assertTrue(form.is_valid(), form._errors)
        error = self.assertRaises(ChassisProblem, form.save)
        self.assertEquals(str(exc), str(error))
