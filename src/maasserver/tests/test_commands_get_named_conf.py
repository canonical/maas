# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the get_named_conf command."""

__all__ = []

from io import StringIO

from django.core.management import call_command
from maasserver.testing.testcase import MAASServerTestCase
from testtools.matchers import (
    Contains,
    FileContains,
)


class TestGetNamedConfCommand(MAASServerTestCase):

    def test_get_named_conf_returns_snippet(self):
        stdout = StringIO()
        call_command('get_named_conf', stdout=stdout)
        result = stdout.getvalue()
        # Just check that the returned snippet looks all right.
        self.assertIn('include "', result)

    def test_get_named_conf_appends_to_config_file(self):
        file_path = self.make_file()
        call_command(
            'get_named_conf', edit=True, config_path=file_path)
        self.assertThat(
            file_path,
            FileContains(
                matcher=Contains('include "')))
