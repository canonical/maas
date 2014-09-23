# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `DeployForm`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.forms import DeployForm
from maasserver.testing.osystems import make_usable_osystem
from maasserver.testing.testcase import MAASServerTestCase


class TestDeployForm(MAASServerTestCase):
    """Tests for `DeployForm`."""

    def test_uses_live_data(self):
        # The DeployForm uses the database rather than just relying on
        # hard-coded stuff.
        osystem = make_usable_osystem(self)
        os_name = osystem['name']
        release_name = osystem['default_release']
        release_name = "%s/%s" % (os_name, release_name)
        deploy_form = DeployForm()
        os_choices = deploy_form.fields['default_osystem'].choices
        os_names = [name for name, title in os_choices]
        release_choices = deploy_form.fields['default_distro_series'].choices
        release_names = [name for name, title in release_choices]
        self.assertIn(os_name, os_names)
        self.assertIn(release_name, release_names)

    def test_accepts_new_values(self):
        osystem = make_usable_osystem(self)
        os_name = osystem['name']
        release_name = osystem['default_release']
        params = {
            'default_osystem': os_name,
            'default_distro_series': "%s/%s" % (os_name, release_name),
            }
        form = DeployForm(data=params)
        self.assertTrue(form.is_valid())
