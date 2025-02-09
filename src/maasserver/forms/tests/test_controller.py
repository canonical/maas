# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for controller forms."""

from maasserver.clusterrpc.driver_parameters import get_driver_choices
from maasserver.forms import ControllerForm
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestControllerForm(MAASServerTestCase):
    def test_Contains_limited_set_of_fields(self):
        form = ControllerForm()

        self.assertEqual(
            {
                "description",
                "zone",
                "domain",
                "power_type",
                "power_parameters",
            },
            form.fields.keys(),
        )

    def test_populates_power_type_choices(self):
        form = ControllerForm()
        self.assertEqual(
            [""] + [choice[0] for choice in get_driver_choices()],
            [choice[0] for choice in form.fields["power_type"].choices],
        )

    def test_populates_power_type_initial(self):
        rack = factory.make_RackController()
        form = ControllerForm(instance=rack)
        self.assertEqual(rack.power_type, form.fields["power_type"].initial)

    def test_sets_power_type(self):
        rack = factory.make_RackController()
        power_type = factory.pick_power_type(but_not=["lxd"])
        form = ControllerForm(
            data={
                "power_type": power_type,
                "power_parameters_skip_check": "true",
            },
            instance=rack,
        )
        rack = form.save()
        self.assertEqual(power_type, rack.power_type)

    def test_sets_power_parameters(self):
        rack = factory.make_RackController()
        power_parameters_field = factory.make_string()
        form = ControllerForm(
            data={
                "power_type": "ipmi",
                "power_parameters_field": power_parameters_field,
                "power_parameters_skip_check": "true",
            },
            instance=rack,
        )
        rack = form.save()
        self.assertEqual(
            power_parameters_field, rack.get_power_parameters()["field"]
        )

    def test_sets_zone(self):
        rack = factory.make_RackController()
        zone = factory.make_zone()
        form = ControllerForm(
            data={"zone": zone.name, "power_parameters_skip_check": "true"},
            instance=rack,
        )
        rack = form.save()
        self.assertEqual(zone.name, rack.zone.name)

    def test_sets_domain(self):
        rack = factory.make_RackController()
        domain = factory.make_Domain()
        form = ControllerForm(
            data={
                "domain": domain.name,
                "power_parameters_skip_check": "true",
            },
            instance=rack,
        )
        rack = form.save()
        self.assertEqual(domain.name, rack.domain.name)
