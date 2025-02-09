# Copyright 2016 Canonical Ltd.  This software is licensed under the GNU Affero
# General Public License version 3 (see the file LICENSE).

"""Tests for `UbuntuForm`."""

from urllib.parse import urlparse

from maasserver.forms import UbuntuForm
from maasserver.rpc.packagerepository import get_archive_mirrors
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestUbuntuForm(MAASServerTestCase):
    """Tests for `UbuntuForm`."""

    def test_form_saves_info_db(self):
        main_url = factory.make_url(scheme="http")
        ports_url = factory.make_url(scheme="http")
        params = {"main_archive": main_url, "ports_archive": ports_url}
        form = UbuntuForm(data=params)
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        self.assertEqual(
            {"main": urlparse(main_url), "ports": urlparse(ports_url)},
            get_archive_mirrors(),
        )

    def test_form_loads_initial_values(self):
        initial_values = {
            "ports_archive": "http://ports.ubuntu.com/ubuntu-ports",
            "main_archive": "http://archive.ubuntu.com/ubuntu",
        }
        form = UbuntuForm()
        self.assertEqual(initial_values, form.initial)
