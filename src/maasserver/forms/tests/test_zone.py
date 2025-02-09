# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `ZoneForm`."""

from maasserver.forms import ZoneForm
from maasserver.models.defaultresource import DefaultResource
from maasserver.models.zone import Zone
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object


class TestZoneForm(MAASServerTestCase):
    """Tests for `ZoneForm`."""

    def test_creates_zone(self):
        name = factory.make_name("zone")
        description = factory.make_string()
        form = ZoneForm(data={"name": name, "description": description})
        form.save()
        zone = Zone.objects.get(name=name)
        self.assertIsNotNone(zone)
        self.assertEqual(description, zone.description)

    def test_updates_zone(self):
        zone = factory.make_Zone()
        new_description = factory.make_string()
        form = ZoneForm(data={"description": new_description}, instance=zone)
        form.save()
        zone = reload_object(zone)
        self.assertEqual(new_description, zone.description)

    def test_renames_zone(self):
        zone = factory.make_Zone()
        new_name = factory.make_name("zone")
        form = ZoneForm(data={"name": new_name}, instance=zone)
        form.save()
        zone = reload_object(zone)
        self.assertEqual(new_name, zone.name)
        self.assertEqual(zone, Zone.objects.get(name=new_name))

    def test_update_default_zone_description_works(self):
        zone = DefaultResource.objects.get_default_zone()
        new_description = factory.make_string()
        form = ZoneForm(data={"description": new_description}, instance=zone)
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        zone = reload_object(zone)
        self.assertEqual(new_description, zone.description)

    def test_allows_renaming_default_zone(self):
        zone = DefaultResource.objects.get_default_zone()
        form = ZoneForm(
            data={"name": factory.make_name("zone")}, instance=zone
        )
        self.assertTrue(form.is_valid(), form.errors)
