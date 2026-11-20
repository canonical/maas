# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `DeployForm`."""

from maasserver.enum import BOOT_RESOURCE_TYPE
from maasserver.forms import DeployForm
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestDeployForm(MAASServerTestCase):
    """Tests for `DeployForm`."""

    def test_uses_live_data(self):
        # The DeployForm uses the database rather than just relying on
        # hard-coded stuff.
        osystem = factory.make_name("osystem")
        release = factory.make_name("release")
        release_name = f"{osystem}/{release}"
        factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED, name=release_name
        )
        deploy_form = DeployForm()
        os_choices = deploy_form.fields["default_osystem"].choices
        os_names = [name for name, title in os_choices]
        release_choices = deploy_form.fields["default_distro_series"].choices
        release_names = [name for name, title in release_choices]
        self.assertIn(osystem, os_names)
        self.assertIn(release_name, release_names)

    def test_accepts_new_values(self):
        osystem = factory.make_name("osystem")
        release = factory.make_name("release")
        release_name = f"{osystem}/{release}"
        factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED, name=release_name
        )
        params = {
            "default_osystem": osystem,
            "default_distro_series": release_name,
        }
        form = DeployForm(data=params)
        self.assertTrue(form.is_valid(), form.errors)
