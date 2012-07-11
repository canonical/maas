# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the get_named_conf command."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from codecs import getwriter
from io import BytesIO

from django.core.management import call_command
from maasserver.testing.testcase import TestCase
from testtools.matchers import (
    Contains,
    FileContains,
    )


class TestGenerateEnlistmentPXE(TestCase):

    def test_get_named_conf_returns_snippet(self):
        out = BytesIO()
        stdout = getwriter("UTF-8")(out)
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
