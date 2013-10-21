# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for import scripts' configuration handling."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import os.path

from maastesting.factory import factory
from provisioningserver.import_images import config as config_module
from provisioningserver.import_images.config import (
    merge_legacy_ephemerals_config,
    parse_legacy_config,
    retire_legacy_config,
    )
from provisioningserver.testing.testcase import PservTestCase
from provisioningserver.utils import ExternalProcessError
from testtools.matchers import (
    FileContains,
    FileExists,
    Not,
    )


def make_var_name():
    """Make up an environment variable name (but don't define the variable)."""
    return factory.make_name('VAR', sep='_')


def make_option_and_value():
    """Make up an environment variable name and value."""
    return make_var_name(), factory.getRandomString()


def make_legacy_config(testcase, options):
    """Create a legacy config file containing the given options.

    The config file will be patched into `parse_legacy_config` for the
    duration of the ongoing test.

    This does not do any kind of escaping.  If you want your value
    single-quoted, for example, add the the quotes in `options`.
    """
    contents = ''.join(
        '%s=%s\n' % (variable, value)
        for variable, value in options.iteritems())
    legacy_config = testcase.make_file(contents=contents.encode('utf-8'))
    testcase.patch(config_module, 'EPHEMERALS_LEGACY_CONFIG', legacy_config)
    return legacy_config


class TestParseLegacyConfig(PservTestCase):

    def test_parses_legacy_config(self):
        variable, value = make_option_and_value()
        make_legacy_config(self, {variable: value})

        self.assertEqual(
            {variable: value},
            parse_legacy_config({variable}))

    def test_returns_unicode(self):
        variable, value = make_option_and_value()
        make_legacy_config(self, {variable: value})

        config = parse_legacy_config({variable})
        self.assertIsInstance(config.keys()[0], unicode)
        self.assertIsInstance(config.values()[0], unicode)

    def test_handles_equals_signs(self):
        variable = make_var_name()
        value = '=with=more=equals=signs'
        make_legacy_config(self, {variable: value})

        self.assertEqual(
            {variable: value},
            parse_legacy_config({variable}))

    def test_handles_multiple_variables(self):
        options = dict(make_option_and_value() for counter in range(4))
        make_legacy_config(self, options)
        self.assertEqual(options, parse_legacy_config(options))

    def test_treats_single_quoted_values_as_single_quoted(self):
        variable = make_var_name()
        value = 'value "with double-quotes" in the middle'
        make_legacy_config(self, {variable: "'%s'" % value})

        self.assertEqual(
            {variable: value},
            parse_legacy_config({variable}))

    def test_treats_double_quoted_values_as_double_quoted(self):
        variable = make_var_name()
        value = "value 'with single-quotes' in the middle"
        make_legacy_config(self, {variable: '"%s"' % value})

        self.assertEqual(
            {variable: value},
            parse_legacy_config({variable}))

    def test_handles_newlines_in_values(self):
        variable = make_var_name()
        value = '\nNEW!\nnow with extra line breaks'
        make_legacy_config(self, {variable: "'%s'" % value})

        self.assertEqual(
            {variable: value},
            parse_legacy_config({variable}))

    def test_skips_unwanted_options(self):
        variable, value = make_option_and_value()
        make_legacy_config(self, dict([
            (variable, value),
            make_option_and_value(),
            make_option_and_value(),
            ]))

        self.assertEqual(
            {variable: value},
            parse_legacy_config({variable}))

    def test_skips_unset_options(self):
        make_legacy_config(self, dict([make_option_and_value()]))
        self.assertEqual({}, parse_legacy_config({make_var_name()}))

    def test_returns_empty_if_there_is_no_legacy_config(self):
        non_config = os.path.join(self.make_dir(), factory.make_name())
        self.patch(config_module, 'EPHEMERALS_LEGACY_CONFIG', non_config)

        self.assertEqual({}, parse_legacy_config({make_var_name()}))

    def test_reports_failure_in_legacy_config(self):
        make_legacy_config(self, {make_var_name(): 'x ; exit 1'})

        self.assertRaises(
            ExternalProcessError,
            parse_legacy_config, dict([make_option_and_value()]))


class TestMergeLegacyEphemeralsConfig(PservTestCase):

    def test_populates_new_config_from_legacy(self):
        arches = [factory.make_name('arch') for counter in range(3)]
        releases = [factory.make_name('release') for counter in range(3)]
        legacy_options = {
            'DATA_DIR': factory.getRandomString(),
            'ARCHES': "'%s'" % ' '.join(arches),
            'RELEASES': "'%s'" % ' '.join(releases),
        }
        make_legacy_config(self, legacy_options)
        config = {'boot': {'ephemeral': {}}}

        changed = merge_legacy_ephemerals_config(config)

        self.assertTrue(changed)
        self.assertEqual(
            {
                'architectures': arches,
                'ephemeral': {
                    'images_directory': legacy_options['DATA_DIR'],
                    'releases': releases,
                },
            },
            config['boot'])

    def test_does_nothing_without_legacy_config(self):
        images_directory = self.make_dir()
        config = {
            'boot': {
                'ephemeral': {
                    'images_directory': images_directory
                }
            }
        }
        make_legacy_config(self, {})

        changed = merge_legacy_ephemerals_config(config)

        self.assertFalse(changed)
        self.assertEqual(
            {'boot': {'ephemeral': {'images_directory': images_directory}}},
            config)

    def test_uses_config_settings_where_no_legacy_value_set(self):
        make_legacy_config(self, {})
        config = {'boot': {'ephemeral': {}}}

        changed = merge_legacy_ephemerals_config(config)

        self.assertFalse(changed)
        self.assertEqual({'boot': {'ephemeral': {}}}, config)

    def test_converts_arch_from_legacy(self):
        legacy_arches = ["amd64/generic", "i386/generic", "armhf/highbank"]
        legacy_options = {'ARCHES': "'%s'" % ' '.join(legacy_arches)}
        new_arches = ["amd64", "i386", "armhf"]
        make_legacy_config(self, legacy_options)
        config = {'boot': {'ephemeral': {}}}
        changed = merge_legacy_ephemerals_config(config)

        self.assertTrue(changed)
        self.assertEqual(
            {
                'architectures': new_arches,
                'ephemeral': {},
            },
            config['boot'])


class TestRetireLegacyConfig(PservTestCase):

    def make_legacy_config(self, text):
        """Set up a legacy config file."""
        legacy_config = self.make_file(contents=text)
        self.patch(config_module, 'EPHEMERALS_LEGACY_CONFIG', legacy_config)
        return legacy_config

    def test_renames_existing_file(self):
        text = factory.getRandomString()
        legacy_config = self.make_legacy_config(text)

        retire_legacy_config()

        self.assertThat(legacy_config, Not(FileExists()))
        self.assertThat(legacy_config + '.obsolete', FileContains(text))

    def test_overwrites_existing_obsolete_file(self):
        text = factory.getRandomString()
        legacy_config = self.make_legacy_config(text)
        obsolete_config = legacy_config + '.obsolete'
        factory.make_file(
            os.path.dirname(obsolete_config),
            os.path.basename(obsolete_config))

        retire_legacy_config()

        self.assertThat(legacy_config, Not(FileExists()))
        self.assertThat(obsolete_config, FileContains(text))
