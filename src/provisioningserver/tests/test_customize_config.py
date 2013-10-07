# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for customize_config."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from argparse import ArgumentParser
from io import BytesIO
import os.path
from subprocess import (
    PIPE,
    Popen,
    )
import sys
from textwrap import dedent

from maastesting import root
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver import customize_config
from provisioningserver.utils import maas_custom_config_markers


class TestCustomizeConfig(MAASTestCase):

    def run_command(self, input_file, stdin):
        self.patch(sys, 'stdin', BytesIO(stdin.encode('utf-8')))
        self.patch(sys, 'stdout', BytesIO())
        parser = ArgumentParser()
        customize_config.add_arguments(parser)
        parsed_args = parser.parse_args((input_file, ))
        customize_config.run(parsed_args)

    def test_runs_as_script(self):
        original_text = factory.getRandomString()
        original_file = self.make_file(original_text)
        script = os.path.join(root, "bin", "maas-provision")
        command = Popen(
            [script, "customize-config", original_file],
            stdin=PIPE, stdout=PIPE,
            env=dict(PYTHONPATH=":".join(sys.path), LC_ALL='en_US.UTF-8'))
        command.communicate(original_text)
        self.assertEqual(0, command.returncode)

    def test_produces_sensible_text(self):
        header, footer = maas_custom_config_markers
        original_file = self.make_file(contents="Original text here.")

        self.run_command(original_file, stdin="Custom section here.")

        sys.stdout.seek(0)
        expected = dedent("""\
            Original text here.
            %s
            Custom section here.
            %s
            """) % (header, footer)
        output = sys.stdout.read()
        self.assertEqual(expected, output.decode('utf-8'))

    def test_does_not_modify_original(self):
        original_text = factory.getRandomString().encode('ascii')
        original_file = self.make_file(contents=original_text)

        self.run_command(original_file, factory.getRandomString())

        with open(original_file, 'rb') as reread_file:
            contents_after = reread_file.read()

        self.assertEqual(original_text, contents_after)
